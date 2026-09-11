# Optional Gemini Backend Workflow

Use only when Gemini is explicitly selected or contextually required and the
execution path is permitted. This reference does not choose the renderer for
other figure tasks.

Use an available, compatible Gemini image model selected for the task.
`gemini-3-pro-image-preview` is a historical example from this skill, not an
assurance of current availability or a required model.

The google-genai package and Gemini credentials are required only for this SDK
route. Do not install packages, activate paid services, or change accounts solely
because this recipe exists. Reuse authorized setup when available; a new
unauthorized paid or credential-backed service requires authorization before use.
Missing setup blocks only this route, not independent specification work.

Credentials may be consumed by the authorized SDK process through its normal
configuration. Do not inspect or print secret values, embed them in scripts,
or include them in prompts, logs, or delivered provenance.

Use the FigureSpec to write the prompt. Include style, layout, exact labels,
connections, and constraints as needed; fixed section order and line counts
are not required. See [diagram-generation.md](diagram-generation.md) for examples.

Each generation call produces one candidate. Inspect it under the main skill's
[QA policy](../SKILL.md#qa-and-iteration). A further call requires a concrete
defect or requested variant. Preserve previous candidates when needed to compare
or diagnose a failure, not to satisfy a fixed count.

Record the selected model, prompt, nonsecret parameters, output artifact, and
relevant limitations. This supports provenance, not guaranteed pixel-identical
reproduction.

## Single-Call SDK Recipe

This is a response-handling fragment, not a standalone executable runner.
Use only with an already authorized configured client, selected model, prompt,
and a fresh destination path with an extension matching the returned image MIME
type. Diagnose empty/error responses without exposing raw credential-bearing logs.
The fragment does not retry, inspect credentials, or mark the candidate QA-passed.

```python
response = client.models.generate_content(
    model=selected_model,
    contents=prompt_text,
    config=genai.types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
    ),
)
parts = response.candidates[0].content.parts if response.candidates else []
image_part = next((part for part in (parts or []) if part.inline_data), None)
if image_part is None:
    raise RuntimeError("No image candidate returned")
# Check image_part.inline_data.mime_type against the selected output extension.
# Exclusive creation preserves existing candidates.
with open(output_path, "xb") as output:
    output.write(image_part.inline_data.data)
# Inspect the saved candidate against FigureSpec before completion or another call.
```
