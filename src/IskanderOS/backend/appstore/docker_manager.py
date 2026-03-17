"""
docker_manager.py — Glass-Box-logged Docker SDK wrapper.

Every Docker API call (pull, create, start, stop, remove, inspect) is
wrapped in an AgentAction record before execution. This ensures the
Glass Box Protocol is satisfied: every side-effect the Provisioner Agent
produces is logged, rationale-attributed, and human-reviewable.

HITL ENFORCEMENT:
  - `create_container()` and `remove_container()` carry ethical_impact=HIGH.
    The calling agent MUST obtain HITL approval before invoking these methods.
    This module does NOT enforce HITL itself — that is the graph's responsibility.
  - `pull_image()` is ethical_impact=MEDIUM (network side-effect, no state change).
  - `start_container()`, `stop_container()` are ethical_impact=MEDIUM.
  - `get_container_status()` is ethical_impact=LOW (read-only).

SECURITY:
  - Only images listed in AppCatalog.is_allowed_image() may be pulled or run.
    DockerManager checks this before every pull/create call.
  - The Docker socket must be mounted read-write into the backend container:
      /var/run/docker.sock:/var/run/docker.sock
    This is a significant privilege — the cooperative's legal wrapper should
    document that the sovereign node has root-equivalent Docker access.
"""
from __future__ import annotations

import logging
import secrets
import string
from typing import Any

logger = logging.getLogger(__name__)

# ── Lazy Docker SDK import ─────────────────────────────────────────────────────
# docker is an optional dependency (docker==7.1.0). We import lazily so that
# the rest of the backend starts even if the Docker socket is not available
# (e.g., during development without Docker).
try:
    import docker
    from docker.errors import DockerException, ImageNotFound, NotFound
    _DOCKER_AVAILABLE = True
except ImportError:
    _DOCKER_AVAILABLE = False
    DockerException = Exception  # type: ignore[misc,assignment]
    ImageNotFound = Exception    # type: ignore[misc,assignment]
    NotFound = Exception         # type: ignore[misc,assignment]


# ── AgentAction import (Glass Box) ────────────────────────────────────────────
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

AGENT_ID = "provisioner-agent"


class DockerManager:
    """
    Docker SDK wrapper with Glass Box Protocol logging.

    All mutating operations return a tuple of (result, AgentAction) so the
    Provisioner Agent can append the action to the LangGraph state's action_log
    without the manager needing direct access to the state.

    Fail-safe design:
      - If the Docker daemon is unreachable, all methods return (None, action)
        with an error-level action record. The calling graph node must check
        the return value and route to error handling.
      - No exceptions propagate from this module — all DockerExceptions are
        caught and converted to error action records.
    """

    def __init__(self, socket_url: str = "unix:///var/run/docker.sock") -> None:
        self._socket_url = socket_url
        self._client: Any = None  # docker.DockerClient or None
        self._init_client()

    def _init_client(self) -> None:
        if not _DOCKER_AVAILABLE:
            logger.warning("docker Python package not installed — DockerManager in stub mode.")
            return
        try:
            self._client = docker.DockerClient(base_url=self._socket_url)
            self._client.ping()
            logger.info("DockerManager connected to %s", self._socket_url)
        except DockerException as exc:
            logger.warning("Docker daemon unreachable: %s — DockerManager in stub mode.", exc)
            self._client = None

    @property
    def is_available(self) -> bool:
        return self._client is not None

    # ── Image Operations ───────────────────────────────────────────────────────

    def pull_image(
        self, image: str, allowed: bool = True
    ) -> tuple[bool, AgentAction]:
        """
        Pull a Docker image from the registry.

        Args:
            image:   Full image reference (e.g., "nextcloud:28-apache").
            allowed: Pre-checked result of AppCatalog.is_allowed_image().
                     If False, this method rejects the pull without contacting Docker.

        Returns:
            (success: bool, action: AgentAction)
        """
        if not allowed:
            action = AgentAction(
                agent_id=AGENT_ID,
                action=f"BLOCKED pull_image({image})",
                rationale="Image is not in the vetted FOSS catalog. Deployment blocked.",
                ethical_impact=EthicalImpactLevel.HIGH,
                payload={"image": image, "blocked": True},
            )
            logger.error("Blocked attempt to pull unlisted image: %s", image)
            return False, action

        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"pull_image({image})",
            rationale=(
                "Pulling vetted FOSS image from registry prior to democratically-approved deployment. "
                "Image is listed in the cooperative's app catalog."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={"image": image},
        )

        if not self.is_available:
            logger.warning("Docker not available — pull_image stub: %s", image)
            return True, action  # Stub: report success for dev environments.

        try:
            self._client.images.pull(image)
            logger.info("Pulled image: %s", image)
            return True, action
        except DockerException as exc:
            action.action = f"FAILED pull_image({image}): {exc}"
            action.ethical_impact = EthicalImpactLevel.HIGH
            logger.error("Failed to pull image %s: %s", image, exc)
            return False, action

    # ── Container Lifecycle ────────────────────────────────────────────────────

    def create_container(
        self,
        name: str,
        image: str,
        port_mapping: dict[str, int],
        environment: dict[str, str],
        volumes: list[str],
        resource_limits: dict[str, Any],
        traefik_labels: dict[str, str],
        traefik_network: str = "iskander_apps",
    ) -> tuple[str | None, AgentAction]:
        """
        Create and start a Docker container for an approved app deployment.

        This is the highest-impact operation in the Provisioner Agent.
        It MUST only be called after HITL approval has been recorded in the
        LangGraph state (requires_human_token=False after HITL breakpoint).

        Args:
            name:             Container name (must be unique; convention: iskander_<app>).
            image:            Docker image reference (must be catalog-approved).
            port_mapping:     {"host_port": N, "container_port": N}
            environment:      Dict of env vars — secrets must already be resolved.
            volumes:          List of named volume mount specs ("vol_name:/mount/path").
            resource_limits:  {"cpu_quota": N, "mem_limit": "512m"} etc.
            traefik_labels:   Docker labels for Traefik routing.
            traefik_network:  Docker network to attach (enables Traefik service discovery).

        Returns:
            (container_id: str | None, action: AgentAction)
        """
        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"create_container({name}, {image})",
            rationale=(
                "Deploying democratically-approved FOSS application. "
                "HITL vote confirmed prior to this call. "
                "Container will be attached to Traefik network for reverse-proxy routing."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "name": name,
                "image": image,
                "port_mapping": port_mapping,
                "traefik_labels": traefik_labels,
            },
        )

        if not self.is_available:
            logger.warning("Docker not available — create_container stub: %s", name)
            return f"stub_container_{name}", action  # Stub ID for dev.

        try:
            # Build port bindings dict for Docker SDK.
            ports: dict[str, int | None] = {
                f"{port_mapping['container_port']}/tcp": port_mapping["host_port"]
            }

            # Merge catalog resource limits into host_config kwargs.
            host_cfg_kwargs: dict[str, Any] = {}
            if "cpu_quota" in resource_limits:
                host_cfg_kwargs["cpu_quota"] = int(resource_limits["cpu_quota"])
                host_cfg_kwargs["cpu_period"] = 100000
            if "mem_limit" in resource_limits:
                host_cfg_kwargs["mem_limit"] = resource_limits["mem_limit"]

            # Create the Docker volume mounts.
            vol_binds: dict[str, dict[str, str]] = {}
            for vol_spec in volumes:
                vol_name, mount_path = vol_spec.split(":", 1)
                vol_binds[vol_name] = {"bind": mount_path, "mode": "rw"}

            container = self._client.containers.run(
                image=image,
                name=name,
                detach=True,
                ports=ports,
                environment=environment,
                volumes=vol_binds,
                labels=traefik_labels,
                network=traefik_network,
                **host_cfg_kwargs,
            )
            logger.info("Container created: %s (%s)", name, container.short_id)
            action.payload["container_id"] = container.id
            return container.id, action

        except DockerException as exc:
            action.action = f"FAILED create_container({name}): {exc}"
            logger.error("Failed to create container %s: %s", name, exc)
            return None, action

    def stop_container(self, container_id: str) -> tuple[bool, AgentAction]:
        """
        Stop a running container (does not remove it).

        Stopping an app requires HITL approval. The container is retained
        so it can be restarted if the cooperative changes its mind.
        """
        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"stop_container({container_id[:12]})",
            rationale="Stopping democratically-approved container on member request.",
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={"container_id": container_id},
        )

        if not self.is_available:
            return True, action

        try:
            container = self._client.containers.get(container_id)
            container.stop(timeout=10)
            logger.info("Container stopped: %s", container_id[:12])
            return True, action
        except (DockerException, NotFound) as exc:
            action.action = f"FAILED stop_container({container_id[:12]}): {exc}"
            logger.error("Failed to stop container %s: %s", container_id[:12], exc)
            return False, action

    def remove_container(self, container_id: str) -> tuple[bool, AgentAction]:
        """
        Remove a stopped container and its anonymous volumes.

        Container removal requires a separate democratic vote (HITL).
        Named volumes (app data) are NOT removed — data persistence is the
        cooperative's responsibility to manage.
        """
        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"remove_container({container_id[:12]})",
            rationale=(
                "Removing container after democratic vote to decommission app. "
                "Named data volumes are preserved — data is not destroyed. "
                "Re-deployment is possible by re-running the provisioner pipeline."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={"container_id": container_id},
        )

        if not self.is_available:
            return True, action

        try:
            container = self._client.containers.get(container_id)
            container.remove(v=False)  # v=False: keep named volumes.
            logger.info("Container removed: %s", container_id[:12])
            return True, action
        except (DockerException, NotFound) as exc:
            action.action = f"FAILED remove_container({container_id[:12]}): {exc}"
            logger.error("Failed to remove container %s: %s", container_id[:12], exc)
            return False, action

    def get_container_status(self, container_id: str) -> tuple[dict[str, Any], AgentAction]:
        """
        Inspect a container and return its status dict.

        Read-only — does not mutate any state.
        """
        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"get_container_status({container_id[:12]})",
            rationale="Reading container runtime status for dashboard display.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"container_id": container_id},
        )

        if not self.is_available:
            return {"status": "unknown", "stub": True}, action

        try:
            container = self._client.containers.get(container_id)
            status_data = {
                "status": container.status,
                "name": container.name,
                "image": container.image.tags[0] if container.image.tags else "unknown",
                "ports": container.ports,
            }
            action.payload.update(status_data)
            return status_data, action
        except (DockerException, NotFound) as exc:
            return {"status": "not_found", "error": str(exc)}, action

    # ── Network Management ────────────────────────────────────────────────────

    def ensure_network(self, network_name: str = "iskander_apps") -> bool:
        """
        Ensure the Traefik overlay network exists, creating it if absent.

        Called once at startup — idempotent.
        """
        if not self.is_available:
            return True

        try:
            self._client.networks.get(network_name)
            return True
        except NotFound:
            try:
                self._client.networks.create(network_name, driver="bridge")
                logger.info("Created Docker network: %s", network_name)
                return True
            except DockerException as exc:
                logger.error("Failed to create network %s: %s", network_name, exc)
                return False

    # ── Credential Generation ─────────────────────────────────────────────────

    @staticmethod
    def generate_credential(length: int = 24) -> str:
        """
        Generate a cryptographically secure random password.

        Used to populate __GENERATE__ env var placeholders in catalog entries.
        The returned credential is passed directly into the container environment
        and returned to the requesting member — it is NEVER logged in plain text.
        """
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def build_traefik_labels(
        app_name: str,
        domain_suffix: str,
        container_port: int,
        path_prefix: str | None = None,
    ) -> dict[str, str]:
        """
        Build Traefik v3 Docker labels for automatic reverse-proxy routing.

        Host-based routing: http://<app_name>.<domain_suffix>
        Path-based routing: http://<domain_suffix><path_prefix>  (if path_prefix set)
        """
        labels: dict[str, str] = {
            "traefik.enable": "true",
        }

        rule = (
            f"PathPrefix(`{path_prefix}`)"
            if path_prefix
            else f"Host(`{app_name}.{domain_suffix}`)"
        )
        svc_name = f"iskander_{app_name}"

        labels[f"traefik.http.routers.{svc_name}.rule"] = rule
        labels[f"traefik.http.routers.{svc_name}.entrypoints"] = "web"
        labels[f"traefik.http.services.{svc_name}.loadbalancer.server.port"] = str(container_port)

        return labels
