# Publication Style Guide for ML Paper Figures

Standards for figure styling across major ML/AI conferences.

## Shared Figure Requirements

Follow [Figure Output Policy](../SKILL.md#figure-output-policy) for format,
priority of requirements, and vector/raster/mixed classification.

- Evaluate raster resolution at final display size. DPI metadata or a PDF
  wrapper alone does not improve image detail or make it vector.
- Use distinguishable encodings, readable text, sufficient contrast, and
  consistent semantics across figures. Do not rely on color alone.
- Make the figure and caption jointly understandable without requiring the
  main text. Preserve necessary panel labels and condition titles.
- Decorative choices may follow the selected style but must not obscure,
  distort, or imply unsupported scientific meaning.

Dimensions, font sizes, template examples, and palettes below are reference
starting points. Check the selected venue/year/template and the actual final
display size. They are not guarantees of current venue compliance.

## Venue-Specific Figure Dimensions

### NeurIPS

| Layout | Width | Notes |
|--------|-------|-------|
| Single column | 5.5 in | NeurIPS is single-column |
| Half width | 2.65 in | Side-by-side within column |
| Max height | 9 in | Full page |

Template: `\usepackage[final]{neurips_2025}`

### ICML

| Layout | Width | Notes |
|--------|-------|-------|
| Single column | 3.25 in | ICML is two-column |
| Full width | 6.75 in | `\begin{figure*}` |
| Max height | 9.25 in | Full page |

Template: `\usepackage{icml2026}`

### ICLR

| Layout | Width | Notes |
|--------|-------|-------|
| Single column | 5.5 in | ICLR is single-column |
| Max height | 9 in | Full page |

Template: `\usepackage{iclr2026_conference}`

### ACL / EMNLP

| Layout | Width | Notes |
|--------|-------|-------|
| Single column | 3.3 in | ACL is two-column |
| Full width | 6.8 in | `\begin{figure*}` |

Template: `\usepackage[hyperref]{acl2025}`

### AAAI

| Layout | Width | Notes |
|--------|-------|-------|
| Single column | 3.3 in | AAAI is two-column |
| Full width | 7.0 in | `\begin{figure*}` |

## Color Palettes

### Recommended Colorblind-Safe Palette

This is a palette example, not a guarantee of accessibility. Check the actual encodings, contrast, grayscale rendering, and redundant markers or labels.

```python
# "deep" variant — high contrast, good for lines and bars
PALETTE_DEEP = [
    "#4C72B0",  # blue
    "#DD8452",  # orange
    "#55A868",  # green
    "#C44E52",  # red
    "#8172B3",  # purple
    "#937860",  # brown
    "#DA8BC3",  # pink
    "#8C8C8C",  # gray
]
```

### Two-Color Schemes (ours vs. baseline)

```python
# High contrast pair
OURS = "#C44E52"     # red — stands out
BASELINE = "#8C8C8C" # gray — recedes

# Alternative pair
OURS = "#4C72B0"     # blue
BASELINE = "#DD8452"  # orange
```

### Gradient Schemes (for heatmaps / continuous data)

| Use Case | Colormap | Code |
|----------|----------|------|
| Single variable (0 to max) | Blues | `cmap="Blues"` |
| Diverging (negative to positive) | RdBu_r | `cmap="RdBu_r"` |
| Perceptually uniform | viridis | `cmap="viridis"` |
| Correlation matrix | coolwarm | `cmap="coolwarm"` |
| Attention weights | YlOrRd | `cmap="YlOrRd"` |

### Colors to Avoid

- **Pure red + pure green** — indistinguishable for ~8% of males
- **Rainbow/jet colormap** — perceptually non-uniform, misleading
- **Light yellow on white** — insufficient contrast
- **Neon/saturated colors** — look unprofessional in academic papers

## Typography

### Font Matching LaTeX Documents

| Conference | Document Font | Figure Font Setting |
|-----------|---------------|-------------------|
| NeurIPS | Times | `font.family: serif`, `font.serif: Times New Roman` |
| ICML | Times | Same as NeurIPS |
| ICLR | Times | Same as NeurIPS |
| ACL | Times | Same as NeurIPS |
| AAAI | Times | Same as NeurIPS |

### Font Size Guidelines

| Element | Size | Rationale |
|---------|------|-----------|
| Axis labels | 10-11pt | Must be readable at print size |
| Tick labels | 8-9pt | Smaller but legible |
| Legend text | 8-9pt | Compact but readable |
| Title (if any) | 11-12pt | Usually omitted (caption serves as title) |
| Annotations | 7-8pt | Smallest readable size |

**Readability guideline**: Aim for at least 7pt text at final print size unless the applicable specification requires otherwise; verify actual readability.

### Math Typesetting

```python
# For inline math
ax.set_xlabel(r"Number of parameters $N$")

# For display math
ax.set_ylabel(r"Loss $\mathcal{L}(\theta)$")

# Greek letters
ax.set_xlabel(r"Learning rate $\alpha$")

# Subscripts/superscripts
ax.set_ylabel(r"$R^2$ score")
```

## Layout Conventions

### Legend Placement

Priority order:
1. **Inside the plot** (upper-left or upper-right) if space allows
2. **Below the plot** with `bbox_to_anchor=(0.5, -0.15), loc="upper center", ncol=N`
3. **To the right** with `bbox_to_anchor=(1.05, 1), loc="upper left"` (takes extra width)

```python
# Clean legend (no frame, no extra spacing)
ax.legend(frameon=False, loc="upper left", handlelength=1.5)

# External legend below
ax.legend(frameon=False, bbox_to_anchor=(0.5, -0.15),
          loc="upper center", ncol=4)
```

### Grid Lines

```python
# Subtle grid (recommended)
ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

# Major grid only (for log-scale plots)
ax.grid(True, which="major", alpha=0.3, linestyle="--")
ax.grid(True, which="minor", alpha=0.1, linestyle=":")
```

### Axis Styling

```python
# Remove top and right spines (clean look)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Reduce tick padding
ax.tick_params(axis="both", which="major", pad=3)
```

### Multi-Panel Labels

```python
# Standard (a), (b), (c) labels
for i, ax in enumerate(axes.flat):
    ax.set_title(f"({chr(97 + i)})", loc="left", fontweight="bold", fontsize=11)

# Or as text annotation
ax.text(-0.1, 1.05, "(a)", transform=ax.transAxes,
        fontsize=12, fontweight="bold", va="top")
```

## Diagram Style Standards

For architecture/system diagrams, regardless of renderer:

### Professional Diagram Palette

```
Section accents:  Blue #4A90D9, Teal #5BA58B, Amber #D4A252, Slate #7B8794
Failure/error:    Red #D94A4A (dashed lines)
Section fill:     #F7F7F5 (very pale warm gray)
Box borders:      #DDDDDD
Box fill:         #FFFFFF
Primary text:     #333333
Secondary text:   #666666
Background:       #FFFFFF
```

### Layout Patterns for Diagrams

| Pattern | When to Use | Description |
|---------|-------------|-------------|
| Horizontal bands | Layered architectures | Sections stacked vertically, boxes horizontal |
| Left-to-right flow | Sequential pipelines | Input → Processing → Output |
| Hub-and-spoke | Central component | Central node with radiating connections |
| Grid | Matrix of components | Regular arrangement for comparison |
| Tree | Hierarchical decisions | Top-down branching structure |

### Arrow Conventions

| Arrow Type | Style | Usage |
|-----------|-------|-------|
| Data flow | Solid, colored by source | Normal information passing |
| Control flow | Solid, gray | Orchestration signals |
| Error/failure | Dashed, red | Failure paths, refutation |
| Optional | Dotted, gray | Conditional paths |
| Bidirectional | Double-headed | Mutual dependencies |

## LaTeX Integration

### Basic Figure Inclusion

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/fig_name.pdf}
  \caption{Clear description of what the figure shows. Best viewed in color.}
  \label{fig:name}
\end{figure}
```

### Full-Width Figure (two-column venues)

```latex
\begin{figure*}[t]
  \centering
  \includegraphics[width=\textwidth]{figures/fig_overview.pdf}
  \caption{System overview showing the three main components.}
  \label{fig:overview}
\end{figure*}
```

### Side-by-Side Subfigures

```latex
\begin{figure}[t]
  \centering
  \begin{subfigure}[b]{0.48\linewidth}
    \centering
    \includegraphics[width=\linewidth]{figures/fig_a.pdf}
    \caption{Training loss}
    \label{fig:a}
  \end{subfigure}
  \hfill
  \begin{subfigure}[b]{0.48\linewidth}
    \centering
    \includegraphics[width=\linewidth]{figures/fig_b.pdf}
    \caption{Evaluation accuracy}
    \label{fig:b}
  \end{subfigure}
  \caption{Training dynamics. (a) Loss decreases steadily. (b) Accuracy plateaus after 50K steps.}
  \label{fig:training}
\end{figure}
```

### Caption Best Practices

- **First sentence**: What the figure shows (standalone understanding)
- **Key takeaway**: What the reader should notice
- **Color note**: A viewing note may help, but required distinctions must also use readable labels, markers, or patterns
- **No "Figure X shows..."** — the figure number is already there

Good: "Training loss across model sizes. Larger models converge faster and to lower final loss."
Bad: "Figure 3 shows the training loss for different model sizes."

## Accessibility Checklist

- [ ] Figures readable in grayscale (print-friendly)
- [ ] Text meets the applicable size requirement and remains readable at final print size
- [ ] Colorblind-safe palette used
- [ ] Different line styles/markers in addition to colors
- [ ] High contrast between data and background
- [ ] Axis labels present and readable
- [ ] Legend clear and non-overlapping
