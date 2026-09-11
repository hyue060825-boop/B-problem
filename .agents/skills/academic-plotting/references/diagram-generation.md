# Diagram Layout and Optional Image-Prompt Recipes

Use only the examples relevant to the selected renderer and FigureSpec.
These are style examples, not provider-selection rules or requirements to add
illustrated objects or facts to the user's scientific content.

## Model Selection

Select the renderer under [the main workflow](../SKILL.md#select-the-rendering-workflow).
Model availability and capability must be checked for the selected backend;
this reference does not rank providers for all technical diagrams.
For Gemini SDK details, use [gemini-backend.md](gemini-backend.md).

## Visual Styles

Use these optional style examples when they fit the user's chosen style and scientific requirements. Keep related figures visually consistent without imposing a style on every figure:

#### Style A: "Sketch / 简笔画" (Hand-Drawn)

Warm, approachable, memorable. Ideal for overview figures and system introductions. Looks like a whiteboard sketch refined by a designer.

```
VISUAL STYLE — HAND-DRAWN SKETCH:
- Slightly irregular, hand-drawn line quality — lines wobble gently, not perfectly straight
- Rounded, soft shapes with visible pen strokes (like drawn with a thick felt-tip marker)
- Warm off-white background (#FAFAF7), NOT pure white
- Fill colors are soft watercolor-like washes: muted blue (#D6E4F0), soft peach (#F5DEB3),
  light sage (#D4E6D4), pale lavender (#E6DFF0)
- Borders are dark charcoal (#2C2C2C) with 2-3px line weight, slightly uneven
- Arrows are hand-drawn with slight curves, ending in simple open arrowheads (not filled triangles)
- Text uses a rounded sans-serif font (like Comic Neue or Architects Daughter feel)
- Small doodle-style icons inside boxes: a tiny gear ⚙ for processing, a lightbulb 💡 for ideas,
  a magnifying glass 🔍 for search — rendered as simple line drawings, NOT emoji
- Overall feel: a carefully drawn whiteboard diagram, clean but with personality
- NO clip art, NO stock icons, NO photorealistic elements
```

#### Style B: "Modern Minimal" (Clean & Bold)

Confident, authoritative. Best for method figures where precision matters.

```
VISUAL STYLE — MODERN MINIMAL:
- Ultra-clean geometric shapes with crisp edges
- Bold color blocks as backgrounds for sections — NOT just accent bars, but full section fills
  using desaturated tones: slate blue (#E8EDF2), warm sand (#F5F0E8), cool mint (#E8F2EE)
- Component boxes have ROUNDED CORNERS (12px radius), NO visible border — they float on
  the section background using subtle shadow (1px, 4px blur, rgba(0,0,0,0.06))
- ONE accent color per section used sparingly on key elements: Deep blue (#2563EB),
  Emerald (#059669), Amber (#D97706), Rose (#E11D48)
- Arrows are thin (1.5px), dark gray (#6B7280), with small filled circle at source
  and clean arrowhead at target — NOT thick colored arrows
- Typography: Inter or system sans-serif, title 600 weight, body 400 weight
- Labels INSIDE boxes, not beside them
- Generous whitespace — at least 24px between elements
- NO decorative elements, NO icons — let the structure speak
```

#### Style C: "Illustrated Technical" (Icon-Rich)

Engaging, explanatory. Good for tutorial-style papers and figures that need to be self-explanatory.

```
VISUAL STYLE — ILLUSTRATED TECHNICAL:
- Each major component has a small MEANINGFUL ICON drawn in a consistent line-art style
  (single color, 2px stroke, ~24x24px): brain icon for reasoning, database cylinder for storage,
  arrow-loop for iteration, network nodes for communication
- Components sit inside soft rounded rectangles with a LEFT COLOR STRIP (4px wide)
- Background is pure white, but each logical group has a very faint colored region behind it
  (#F8FAFC for blue group, #FFF8F0 for orange group)
- Connections use CURVED bezier paths (not straight lines), colored by SOURCE component
- Key data flows are THICKER (3px) than secondary flows (1px, dashed)
- Small annotation badges on arrows: "×N" for repeated operations, "optional" in italics
- Title labels are ABOVE each section in small caps, letter-spaced
- Overall: like a well-designed API documentation diagram
```

#### Style D: "Accent Bar" (Classic Academic)

A classic academic style; check its suitability and grayscale readability for the selected venue and figure.

```
VISUAL STYLE — CLASSIC ACCENT BAR:
- Horizontal section bands stacked vertically, pale gray (#F7F7F5) fill
- Thick colored LEFT ACCENT BAR (8px) distinguishes each section
- Content boxes: white fill, thin #DDD border, 4px rounded corners
- Section palette: Blue #4A90D9, Teal #5BA58B, Amber #D4A252, Slate #7B8794
- Sans-serif typography (Helvetica/Arial), bold titles, regular body
- Colored arrows match their SOURCE section
- Clean, flat, zero decoration
```

## Curated Color Palettes

**"Ocean Dusk"** (optional palette; check actual accessibility):
`#264653` deep teal, `#2A9D8F` teal, `#E9C46A` gold, `#F4A261` sandy orange, `#E76F51` burnt coral

**"Ink & Wash"** (for 简笔画 style):
`#2C2C2C` charcoal ink, `#D6E4F0` washed blue, `#F5DEB3` washed wheat, `#D4E6D4` washed sage, `#E6DFF0` washed lavender

**"Nord"** (for modern minimal):
`#2E3440` polar night, `#5E81AC` frost blue, `#A3BE8C` aurora green, `#EBCB8B` aurora yellow, `#BF616A` aurora red

**"Okabe-Ito"** (recommended accessibility-oriented palette; validate actual contrast and encodings):
`#E69F00` orange, `#56B4E9` sky blue, `#009E73` green, `#F0E442` yellow, `#0072B2` blue, `#D55E00` vermillion, `#CC79A7` pink

---


## Prompt Architecture (Optional Organization)

Use these fields as needed. There is no required section order or line count.
Preserve exact scientific labels and connections; scale detail to figure complexity.

### Section 1: Framing

Set the tone and context. This shapes the model's entire approach.

**For Sketch/简笔画 style**:
```
Create a warm, hand-drawn-style technical diagram for a NeurIPS machine learning
paper. The diagram should feel like a carefully drawn whiteboard sketch —
approachable and clear, with personality in the line work, but still precise
enough for a top venue. Think: the kind of diagram a brilliant researcher would
draw during a coffee chat to explain their system.
```

**For Modern Minimal style**:
```
Create an ultra-clean, modern technical architecture diagram for an ICML paper.
The diagram should feel like a premium design system — confident, spacious, and
authoritative. Think: Apple's developer documentation meets a Nature paper.
Every element earns its space. No visual noise.
```

**For Illustrated Technical style**:
```
Create a richly illustrated technical diagram for an ICLR paper. Each component
should have a small, meaningful line-art icon that helps the reader instantly
understand its purpose. The diagram should be self-explanatory — a reader should
grasp the system architecture just by looking at the figure, before reading the
caption. Think: the best technical documentation you've ever seen.
```

### Section 2: Visual Style

Use the selected visual style as an example, adding only detail needed to satisfy the specification. Scientific correctness takes precedence over style.

**Key principle**: Describe the *feeling* and *materiality*, not just the geometry.

Good: "Lines should wobble gently like drawn with a thick felt-tip marker on smooth paper"
Bad: "Lines should be slightly irregular"

Good: "Fill colors are soft watercolor-like washes — imagine diluted ink bleeding into damp paper"
Bad: "Use light colors"

Good: "Components float on the background with barely-there shadows (1px offset, 6px blur, 3% opacity)"
Bad: "Add subtle shadows"

### Section 3: Color Palette

Specify exact hex codes when the chosen palette requires them. Otherwise choose accessible colors consistent with the paper.

**"Ocean Dusk" palette** (professional, calming):
```
COLOR PALETTE (use EXACTLY these colors, no substitutions):
- Primary components: Deep Teal #264653
- Secondary components: Teal #2A9D8F
- Accent / highlights: Gold #E9C46A
- Warm connections: Sandy Orange #F4A261
- Alert / error paths: Burnt Coral #E76F51
- Backgrounds: Warm off-white #FAFAF7
- Text primary: Nearly black #1A1A2E
- Text secondary: Warm gray #6B7280
- Borders (if any): Soft gray #E5E7EB
```

**"Ink & Wash" palette** (for 简笔画):
```
COLOR PALETTE — INK AND WASH:
- All outlines and text: Charcoal ink #2C2C2C
- Wash fill 1: Diluted blue #D6E4F0 (like watercolor blue, very soft)
- Wash fill 2: Warm wheat #F5DEB3 (like tea-stained paper)
- Wash fill 3: Soft sage #D4E6D4 (like pale green ink wash)
- Wash fill 4: Faint lavender #E6DFF0 (like diluted purple ink)
- Background: Warm paper #FAFAF7 (NOT pure white — should feel like quality drawing paper)
- Accent marks: Terracotta #C0725E (used sparingly for emphasis)
```

**"Nord" palette** (for modern minimal):
```
COLOR PALETTE — NORD:
- Primary: Polar Night #2E3440
- Section fills: Snow Storm #ECEFF4, #E5E9F0, #D8DEE9
- Accent Blue: Frost #5E81AC
- Accent Green: Aurora #A3BE8C
- Accent Yellow: Aurora #EBCB8B
- Accent Red: Aurora #BF616A
- Text: Polar Night #2E3440
- Subtle text: #4C566A
```

### Section 4: Layout Description

Describe required entities, labels, relationships, and meaningful grouping sufficiently precisely. The amount of detail should match figure complexity.

Rules for writing layout descriptions:
1. **Name every box** with exact text content
2. **Specify spatial relationships** explicitly ("Box A is to the LEFT of Box B")
3. **Include subtitles/descriptions** for each component
4. **Describe grouping** ("These 3 boxes are inside a section labeled X")
5. **Specify dimensions** relatively ("roughly 2:1 width-to-height ratio")

**Example (Sketch/简笔画 style)**:
```
LAYOUT — THREE-STAGE PIPELINE (left to right):

The diagram flows LEFT to RIGHT across three main stages, with a feedback loop
curving back from right to left at the bottom.

STAGE 1 — "Observe" (left third of diagram):
- Draw a rounded blob (not a rectangle!) with soft blue wash fill (#D6E4F0)
- Inside the blob: hand-drawn icon of an EYE (simple line drawing, 3 curved lines)
- Below the icon: "Observe" in bold charcoal
- Below that: "Gather signals from environment" in smaller text
- A small stack of paper sheets icon to the lower-right of the blob,
  labeled "Raw Data" with a tiny arrow pointing into the blob

STAGE 2 — "Hypothesize" (middle third):
- Draw a rounded blob with warm wheat wash fill (#F5DEB3)
- Inside: hand-drawn LIGHTBULB icon (simple: circle + filament lines + base)
- Below: "Hypothesize" in bold
- Below: "Form testable predictions" in smaller text
- Two small thought-bubble circles trailing from the blob upward,
  suggesting the thinking process

STAGE 3 — "Verify" (right third):
- Draw a rounded blob with sage wash fill (#D4E6D4)
- Inside: hand-drawn CHECKMARK icon (a satisfying thick check)
- Below: "Verify" in bold
- Below: "Test against evidence" in smaller text

FEEDBACK LOOP:
- A long curved dashed arrow from "Verify" back to "Observe",
  curving BELOW the three stages
- Label on the arrow: "refine & iterate" in italic
- The arrow should feel like a casual hand-drawn curve, not a geometric arc
```

### Section 5: Connections

Describe every arrow individually. Arrows carry the semantic meaning of diagrams.

**Per-arrow specification template**:
```
ARROW [N]: [Source] → [Target]
- Style: [solid / dashed / dotted]
- Color: [hex code]
- Weight: [thin 1px / medium 2px / thick 3px]
- Routing: [straight / curves UP / curves DOWN / bezier around X]
- Label: "[text]" in [italic / bold], positioned [above / below / alongside]
- Arrowhead: [filled triangle / open chevron / circle dot]
```

**Style-specific arrow conventions**:

| Style | Arrow Character |
|-------|----------------|
| Sketch/简笔画 | Hand-drawn curves, open arrowheads, labels in casual handwriting |
| Modern Minimal | Thin gray (#6B7280) straight lines, small filled dot at source, clean chevron at target |
| Illustrated | Colored bezier curves matching source, medium weight, label badges |
| Classic Academic | Solid colored lines matching source section, filled triangle heads |

### Section 6: Constraints

Adapt constraints to the chosen style:

**For Sketch/简笔画**:
```
CONSTRAINTS:
- Lines should look HAND-DRAWN but still legible — wobbly, not chaotic
- NO clip art, NO stock icons, NO photorealistic elements
- NO emoji — icons must be simple LINE DRAWINGS in charcoal
- NO figure numbers, NO captions, NO watermarks
- Background is warm off-white #FAFAF7, NOT pure white
- Overall composition should feel warm and inviting, like a sketchbook page
- Every text label spelled EXACTLY as specified
- Publication quality — this is for NeurIPS, not a napkin sketch
```

**For Modern Minimal**:
```
CONSTRAINTS:
- ZERO decoration — no icons, no illustrations, no ornaments
- NO visible borders on component boxes — they float using subtle shadow only
- NO thick colored lines — all connections are thin gray
- NO gradients, NO patterns, NO textures
- Whitespace is a design element — at least 24px between all elements
- NO figure numbers, NO captions, NO watermarks
- Background pure white #FFFFFF
- Every text label spelled EXACTLY as specified
```

## Complete Prompt Examples

### Example 1: Agent System (Sketch/简笔画 Style)

```
Create a warm, hand-drawn-style technical diagram for a NeurIPS paper showing
an autonomous research agent system. The diagram should feel like a carefully
drawn whiteboard sketch — approachable yet precise.

VISUAL STYLE — HAND-DRAWN SKETCH:
- Slightly irregular, hand-drawn line quality — lines wobble gently, not perfectly straight
- Rounded, soft shapes with visible pen strokes (like drawn with a thick felt-tip marker)
- Warm off-white background (#FAFAF7)
- Fill colors are soft watercolor washes: blue #D6E4F0, wheat #F5DEB3, sage #D4E6D4
- Borders are charcoal #2C2C2C, 2-3px, slightly uneven
- Arrows hand-drawn with natural curves, open arrowheads
- Small doodle-style line-art icons inside each component (NOT emoji, NOT clip art)
- Text in rounded sans-serif, warm and readable

COLOR PALETTE — INK AND WASH:
- Outlines/text: Charcoal #2C2C2C
- Planner fill: Blue wash #D6E4F0
- Executor fill: Wheat wash #F5DEB3
- Verifier fill: Sage wash #D4E6D4
- Background: Warm paper #FAFAF7
- Failure/retry: Terracotta #C0725E

LAYOUT — TRIANGULAR ARRANGEMENT:
Three rounded blob shapes arranged in a triangle:

TOP CENTER — "Planner" blob:
- Blue wash fill (#D6E4F0)
- Line-art icon: a small COMPASS or MAP (simple 2D line drawing)
- Bold label: "Planner"
- Subtitle: "Decomposes research questions"

BOTTOM LEFT — "Executor" blob:
- Wheat wash fill (#F5DEB3)
- Line-art icon: a small GEAR or WRENCH
- Bold label: "Executor"
- Subtitle: "Runs experiments & tools"

BOTTOM RIGHT — "Verifier" blob:
- Sage wash fill (#D4E6D4)
- Line-art icon: a small MAGNIFYING GLASS
- Bold label: "Verifier"
- Subtitle: "Checks results & evidence"

ARROWS:
1. Planner → Executor: curved arrow going DOWN-LEFT, charcoal, solid
   Label: "task plan" (italic, small)
2. Executor → Verifier: curved arrow going RIGHT, charcoal, solid
   Label: "raw results" (italic, small)
3. Verifier → Planner: curved arrow going UP-LEFT, terracotta #C0725E, DASHED
   Label: "needs revision" (italic, small)
   This is the feedback/retry path — dashed to show it's conditional

CENTER of triangle: small text "Shared Memory" with a tiny notebook icon

CONSTRAINTS:
- Hand-drawn feel but still publication quality for NeurIPS
- NO clip art, NO stock icons — only simple line drawings
- NO figure numbers, NO captions
- Warm off-white background, NOT pure white
- Every label spelled EXACTLY as written
```

### Example 2: Training Pipeline (Modern Minimal Style)

```
Create an ultra-clean, modern technical architecture diagram for an ICML paper.
Confident, spacious, authoritative. Think: Apple developer docs meets Nature paper.

VISUAL STYLE — MODERN MINIMAL:
- Ultra-clean geometric shapes with crisp edges
- Bold color blocks as section fills using desaturated tones
- Component boxes: 12px rounded corners, NO visible border, float on section
  background with subtle shadow (1px, 4px blur, rgba(0,0,0,0.06))
- ONE accent color per section, used on section header only
- Arrows: thin 1.5px, dark gray #6B7280, small filled circle at source,
  clean open chevron at target
- Typography: system sans-serif, titles 600 weight, body 400 weight
- Labels INSIDE boxes, generous whitespace (24px+ between elements)

COLOR PALETTE — NORD:
- Deep text: #2E3440
- Section 1 fill: #EEF1F6 (blue tint), accent: #5E81AC
- Section 2 fill: #EDF3ED (green tint), accent: #A3BE8C
- Section 3 fill: #F5F2EA (yellow tint), accent: #EBCB8B
- Box fill: White #FFFFFF
- Arrows: #6B7280

LAYOUT — THREE HORIZONTAL SECTIONS:
Three wide horizontal bands, stacked vertically with 16px gaps.
Each section is a full-width rounded rectangle (8px corners).

[SECTION 1 — "Data" — blue tint background #EEF1F6]
- Small section header top-left: "DATA" in #5E81AC, small caps, letter-spaced
- Three white floating boxes in a row:
  Box: "Corpus" / "1.2T tokens"
  Box: "Filter" / "Quality + dedup"
  Box: "Tokenize" / "BPE 32K"

[SECTION 2 — "Train" — green tint background #EDF3ED]
- Header: "TRAIN" in #A3BE8C
- Three white floating boxes:
  Box: "Model" / "7B · 32 layers"
  Box: "Optimize" / "AdamW · cosine"
  Box: "Checkpoint" / "Every 1K steps"

[SECTION 3 — "Evaluate" — yellow tint background #F5F2EA]
- Header: "EVALUATE" in #EBCB8B
- Three white floating boxes:
  Box: "Benchmark" / "MMLU · HumanEval"
  Box: "Analyze" / "Scaling curves"
  Box: "Report" / "Camera-ready"

ARROWS:
1. "Tokenize" → "Model": thin gray #6B7280, vertical, label "feeds"
2. "Checkpoint" → "Benchmark": thin gray, vertical, label "evaluate"
3. "Analyze" → "Report": thin gray, horizontal, label "publish"

CONSTRAINTS:
- ZERO decoration — no icons, no illustrations
- NO visible box borders — shadow only
- Generous whitespace between all elements
- NO figure numbers, NO captions, NO watermarks
- Background: pure white #FFFFFF
- All labels EXACTLY as written
- Publication quality for ICML 2026
```

## Candidate QA

Apply [QA and Iteration](../SKILL.md#qa-and-iteration) to the first candidate and
every repair. Incorrect scientific content, missing components/connections, wrong
labels, or unreadable required text fail QA regardless of style quality.

Compare aesthetics only among scientifically valid candidates when comparison
is requested or useful. No number of candidates is a substitute for QA.

For each failure, record the defect and target the correction:
- text defect: correct the exact label;
- structure defect: correct the entity, edge, direction, or grouping;
- layout defect: correct overlap, routing, clipping, or final-size readability;
- style defect: adjust the selected treatment without changing meaning.

## TikZ Alternative (for LaTeX-native diagrams)

Use when the diagram is simple enough for deterministic output:

```latex
\begin{tikzpicture}[
    box/.style={draw=#1, fill=#1!8, rounded corners=6pt, minimum width=2.8cm,
                minimum height=1cm, font=\small\sffamily, line width=0.8pt},
    lbl/.style={font=\scriptsize\sffamily\itshape, text=#1},
    arr/.style={-{Stealth[length=5pt]}, line width=0.8pt, color=#1},
]
    \node[box=teal]   (plan) at (0,0)    {Planner};
    \node[box=orange]  (exec) at (4,0)    {Executor};
    \node[box=olive]   (veri) at (8,0)    {Verifier};

    \draw[arr=gray]  (plan) -- (exec) node[midway, above, lbl=gray] {task plan};
    \draw[arr=gray]  (exec) -- (veri) node[midway, above, lbl=gray] {results};
    \draw[arr=red!60, dashed] (veri) to[bend right=30]
        node[midway, below, lbl=red!60] {revise} (plan);
\end{tikzpicture}
```

## Mermaid for Quick Prototyping

Use Mermaid to specify or render logical flow when it fits the output requirements:

```mermaid
graph LR
    A[Observe] --> B[Hypothesize]
    B --> C[Verify]
    C -.->|refine| A
```

Validate the structure, then finish with a suitable renderer or use the validated specification in the selected image backend.
