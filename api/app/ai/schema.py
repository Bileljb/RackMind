"""The contract for the LLM's answer.

Used twice: its JSON Schema is sent to Groq ("strict" structured output, so generation is
constrained to this shape), and Pydantic validates the reply against it again. Never trust
the model to have followed instructions: an answer that doesn't validate is stored as a
failure, never shown as a diagnosis.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Evidence must point at a metric we actually measure, so the UI can link and label it.
MetricName = Literal[
    "cpu_temp", "power_w", "cpu_usage_pct", "disk_used_pct", "memory_used_pct", "network_mbps"
]

Sentence = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class EvidenceItem(BaseModel):
    # extra="forbid" becomes `"additionalProperties": false` in the schema: strict mode needs it.
    model_config = ConfigDict(extra="forbid")

    metric: MetricName
    observation: Sentence = Field(
        description="A fact from the provided data, with its numbers, e.g. 'cpu_temp rose from "
        "45.2 to 78.9 °C over 12 min'. Never a value that is not in the data."
    )


class DiagnosisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probable_cause: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)
    ] = Field(description="The most likely cause, in one or two sentences.")
    confidence: float = Field(
        ge=0, le=1, description="How sure, from 0 to 1, following the calibration rules."
    )
    recommended_steps: list[Sentence] = Field(
        min_length=1,
        max_length=5,
        description="Ordered next steps for a human. Safe checks first; disruptive actions "
        "start with 'Requires approval:'.",
    )
    evidence: list[EvidenceItem] = Field(
        min_length=1, max_length=5, description="The observations that support the cause."
    )
