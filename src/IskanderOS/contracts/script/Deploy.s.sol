// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/**
 * @title  Deploy
 * @notice Foundry deployment script for all Iskander contracts.
 *
 * Supports both local Anvil and Gnosis Chain deployment.
 *
 * Local (Anvil):
 *   forge script script/Deploy.s.sol \
 *     --rpc-url http://localhost:8545 \
 *     --broadcast \
 *     --private-key $DEPLOYER_PRIVATE_KEY \
 *     -vvvv
 *
 * Gnosis Chain:
 *   forge script script/Deploy.s.sol \
 *     --rpc-url $GNOSIS_RPC_URL \
 *     --broadcast \
 *     --verify \
 *     --private-key $DEPLOYER_PRIVATE_KEY \
 *     -vvvv
 *
 * Environment variables (set in .env or shell):
 *   DEPLOYER_PRIVATE_KEY   — Anvil account #0 key (dev) or real deployer key
 *   COOP_NAME              — e.g. "Sunrise Worker Co-op"
 *   LEGAL_WRAPPER_CID      — IPFS CID of ratified legal wrapper
 *   STEWARD_ADDRESS        — Safe multi-sig address (or EOA for dev)
 *   MAX_PAY_RATIO_SCALED   — e.g. 600 for 6:1 (default: 600)
 *   BRIGHTID_VERIFIER      — BrightID verifier address (address(0) for dev)
 *   BRIGHTID_APP_CONTEXT   — BrightID app context bytes32 (bytes32(0) for dev)
 *   MACI_COORDINATOR       — MACI coordinator address (defaults to steward)
 *   SNARK_VERIFIER         — MACI SNARK verifier address (address(0) for dev)
 *   MACI_QUORUM_BPS        — MACI quorum in basis points (default: 5100 = 51%)
 *   STEWARDSHIP_ORACLE     — Oracle address for Impact Score updates (defaults to steward)
 *   STEWARD_THRESHOLD_BPS  — Steward eligibility threshold in basis points (default: 2500 = 25%)
 *   SOLVENCY_FACTOR_BPS    — Circuit breaker solvency ratio in basis points (default: 10000 = 1:1)
 */

import {Script, console2} from "forge-std/Script.sol";
import {CoopIdentity}      from "../src/CoopIdentity.sol";
import {InternalPayroll}   from "../src/InternalPayroll.sol";
import {IskanderEscrow}    from "../src/IskanderEscrow.sol";
import {ArbitrationRegistry} from "../src/ArbitrationRegistry.sol";
import {MACIVoting}        from "../src/governance/MACIVoting.sol";
import {StewardshipLedger} from "../src/governance/StewardshipLedger.sol";
import {ForeignReputation} from "../src/governance/ForeignReputation.sol";
import {TrustRegistry}     from "../src/governance/TrustRegistry.sol";
import {Constitution}      from "../src/Constitution.sol";

contract Deploy is Script {

    function run() external {
        // ── Read config from environment ──────────────────────────────────────
        uint256 deployerKey      = vm.envUint("DEPLOYER_PRIVATE_KEY");
        string  memory coopName  = vm.envOr("COOP_NAME", string("Iskander Co-op [DEV]"));
        string  memory cidStr    = vm.envOr(
            "LEGAL_WRAPPER_CID",
            string("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi") // placeholder CID
        );
        address steward          = vm.envOr("STEWARD_ADDRESS", vm.addr(deployerKey));
        uint256 maxRatio         = vm.envOr("MAX_PAY_RATIO_SCALED", uint256(600));

        // Phase 17: BrightID integration parameters
        address brightIdVerifier = vm.envOr("BRIGHTID_VERIFIER", address(0));
        bytes32 brightIdContext  = vm.envOr("BRIGHTID_APP_CONTEXT", bytes32(0));

        // Phase 12: MACI ZK-Democracy parameters
        address maciCoordinator  = vm.envOr("MACI_COORDINATOR", steward);
        address snarkVerifier    = vm.envOr("SNARK_VERIFIER", address(0));
        uint16  quorumBps        = uint16(vm.envOr("MACI_QUORUM_BPS", uint256(5100)));

        // Phase 23: Stewardship Council parameters
        address stewardshipOracle    = vm.envOr("STEWARDSHIP_ORACLE", steward);
        uint256 stewardThresholdBps  = vm.envOr("STEWARD_THRESHOLD_BPS", uint256(2500));
        uint256 solvencyFactorBps    = vm.envOr("SOLVENCY_FACTOR_BPS", uint256(10000));

        // Diplomatic Embassy: Foreign Reputation System parameters
        address frsOracle              = vm.envOr("FRS_ORACLE", steward);
        uint256 frsQuarantineBps       = vm.envOr("FRS_QUARANTINE_BPS", uint256(1000));
        uint256 frsProvisionalBps      = vm.envOr("FRS_PROVISIONAL_BPS", uint256(3000));
        uint256 frsTrustedBps          = vm.envOr("FRS_TRUSTED_BPS", uint256(7000));

        address deployer = vm.addr(deployerKey);
        console2.log("Deployer           :", deployer);
        console2.log("Coop Name          :", coopName);
        console2.log("Legal CID          :", cidStr);
        console2.log("Steward            :", steward);
        console2.log("Max Pay Ratio      :", maxRatio, "/ 100");
        console2.log("BrightID Verifier  :", brightIdVerifier);
        console2.log("MACI Coordinator   :", maciCoordinator);
        console2.log("Quorum BPS         :", quorumBps);

        vm.startBroadcast(deployerKey);

        // ── 1. Deploy CoopIdentity (ERC-4973 Soulbound Token) ────────────────
        CoopIdentity identity = new CoopIdentity(
            coopName,
            cidStr,
            steward,
            brightIdVerifier,
            brightIdContext
        );
        console2.log("CoopIdentity       :", address(identity));

        // ── 2. Deploy InternalPayroll (Mondragon pay ratio guard) ────────────
        InternalPayroll payroll = new InternalPayroll(
            address(identity),
            steward,
            maxRatio
        );
        console2.log("InternalPayroll    :", address(payroll));

        // ── 3. Deploy IskanderEscrow (inter-coop escrow) ─────────────────────
        // NOTE: ArbitrationRegistry not yet deployed — pass address(0) and wire
        // post-deploy via setArbitrationRegistry().
        IskanderEscrow escrow = new IskanderEscrow(
            address(identity),
            address(0) // wired in step 5
        );
        console2.log("IskanderEscrow     :", address(escrow));

        // ── 4. Deploy ArbitrationRegistry (federated jury arbitration) ───────
        ArbitrationRegistry arbitration = new ArbitrationRegistry(
            address(identity),
            address(escrow),
            steward // operator = steward Safe
        );
        console2.log("ArbitrationRegistry:", address(arbitration));

        // ── 5. Wire cross-contract references ────────────────────────────────
        // Escrow needs ArbitrationRegistry for dispute resolution.
        escrow.setArbitrationRegistry(address(arbitration));
        console2.log("  -> Escrow.setArbitrationRegistry done");

        // CoopIdentity needs ArbitrationRegistry for trust score management.
        identity.setArbitrationRegistry(address(arbitration));
        console2.log("  -> Identity.setArbitrationRegistry done");

        // ── 6. Deploy MACIVoting (ZK-Democracy governance) ──────────────────
        MACIVoting maci = new MACIVoting(
            address(identity),
            maciCoordinator,
            snarkVerifier,
            quorumBps
        );
        console2.log("MACIVoting         :", address(maci));

        // ── 7. Deploy StewardshipLedger (Phase 23: delegation & Impact Scores) ─
        StewardshipLedger stewardshipLedger = new StewardshipLedger(
            address(identity),
            address(escrow),
            stewardshipOracle,
            stewardThresholdBps,
            solvencyFactorBps
        );
        console2.log("StewardshipLedger  :", address(stewardshipLedger));

        // ── 8. Deploy ForeignReputation (Diplomatic Embassy — FRS) ────────────
        ForeignReputation foreignReputation = new ForeignReputation(
            address(identity),
            frsOracle,
            frsQuarantineBps,
            frsProvisionalBps,
            frsTrustedBps
        );
        console2.log("ForeignReputation  :", address(foreignReputation));

        // ── 9. Deploy TrustRegistry (Credential Embassy — issuer key registry) ──
        TrustRegistry trustRegistry = new TrustRegistry(address(identity));
        console2.log("TrustRegistry      :", address(trustRegistry));

        // ── 10. Deploy Constitution (genesis anchor — conditional) ───────────
        string memory genesisCID = vm.envOr("GENESIS_CID", string(""));
        string memory constitutionCID = vm.envOr("CONSTITUTION_CID", string(""));
        uint16 founderCnt = uint16(vm.envOr("FOUNDER_COUNT", uint256(1)));

        Constitution constitution;
        if (bytes(genesisCID).length > 0) {
            constitution = new Constitution(
                genesisCID,
                constitutionCID,
                founderCnt,
                address(identity)
            );
            console2.log("Constitution       :", address(constitution));

            // Wire cross-contract reference
            identity.setConstitution(address(constitution));
            console2.log("  -> Identity.setConstitution done");
        }

        vm.stopBroadcast();

        // ── 8. Write deployment artefact to JSON ─────────────────────────────
        string memory json = string(abi.encodePacked(
            '{\n',
            '  "chainId": ',              vm.toString(block.chainid),            ',\n',
            '  "coopName": "',            coopName,                              '",\n',
            '  "legalWrapperCID": "',     cidStr,                                '",\n',
            '  "steward": "',             vm.toString(steward),                  '",\n',
            '  "CoopIdentity": "',        vm.toString(address(identity)),        '",\n',
            '  "InternalPayroll": "',     vm.toString(address(payroll)),         '",\n',
            '  "IskanderEscrow": "',      vm.toString(address(escrow)),          '",\n',
            '  "ArbitrationRegistry": "', vm.toString(address(arbitration)),     '",\n',
            '  "MACIVoting": "',          vm.toString(address(maci)),            '",\n',
            '  "StewardshipLedger": "',   vm.toString(address(stewardshipLedger)), '",\n',
            '  "ForeignReputation": "',   vm.toString(address(foreignReputation)), '",\n',
            '  "TrustRegistry": "',       vm.toString(address(trustRegistry)),      '"\n',
            '}'
        ));
        vm.writeFile("script/deployment.json", json);
        console2.log("\nDeployment artefact written to script/deployment.json");
    }
}
