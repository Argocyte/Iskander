{{/*
Iskander Helm helpers
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "iskander.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "iskander.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart label.
*/}}
{{- define "iskander.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
Note: cooperative name goes in annotations (iskander.labels.annotations), not
labels, because Kubernetes label values forbid spaces and other characters
that cooperative names legitimately contain.
*/}}
{{- define "iskander.labels" -}}
helm.sh/chart: {{ include "iskander.chart" . }}
app.kubernetes.io/name: {{ include "iskander.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Common annotations — carries human-readable fields that labels cannot.
*/}}
{{- define "iskander.annotations" -}}
iskander.coop/cooperative: {{ .Values.global.cooperative.name | quote }}
{{- end }}

{{/*
Selector labels (stable subset used by Deployments and Services).
*/}}
{{- define "iskander.selectorLabels" -}}
app.kubernetes.io/name: {{ include "iskander.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Namespace name (defaults to "iskander").
*/}}
{{- define "iskander.namespace" -}}
{{- .Values.namespace.name | default "iskander" }}
{{- end }}

{{/*
PostgreSQL host (global override or Bitnami chart service name).
*/}}
{{- define "iskander.postgresql.host" -}}
{{- .Values.global.postgresql.host | default (printf "%s-postgresql" .Release.Name) }}
{{- end }}

{{/*
Redis host.
*/}}
{{- define "iskander.redis.host" -}}
{{- .Values.global.redis.host | default (printf "%s-redis-master" .Release.Name) }}
{{- end }}
