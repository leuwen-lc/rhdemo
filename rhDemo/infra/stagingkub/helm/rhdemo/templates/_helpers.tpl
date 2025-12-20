{{/*
Expand the name of the chart.
*/}}
{{- define "rhdemo.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "rhdemo.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "rhdemo.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rhdemo.labels" -}}
helm.sh/chart: {{ include "rhdemo.chart" . }}
{{ include "rhdemo.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
environment: {{ .Values.global.environment }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "rhdemo.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rhdemo.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
PostgreSQL RHDemo labels
*/}}
{{- define "postgresql-rhdemo.labels" -}}
{{ include "rhdemo.labels" . }}
app.kubernetes.io/component: database
app.kubernetes.io/part-of: rhdemo
{{- end }}

{{/*
PostgreSQL Keycloak labels
*/}}
{{- define "postgresql-keycloak.labels" -}}
{{ include "rhdemo.labels" . }}
app.kubernetes.io/component: database
app.kubernetes.io/part-of: keycloak
{{- end }}

{{/*
Keycloak labels
*/}}
{{- define "keycloak.labels" -}}
{{ include "rhdemo.labels" . }}
app.kubernetes.io/component: identity-provider
app.kubernetes.io/part-of: rhdemo
{{- end }}

{{/*
RHDemo App labels
*/}}
{{- define "rhdemo-app.labels" -}}
{{ include "rhdemo.labels" . }}
app.kubernetes.io/component: application
app.kubernetes.io/part-of: rhdemo
{{- end }}
