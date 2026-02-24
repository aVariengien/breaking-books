# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Keep this file up to date.** When you add new schemas, templates, tools, or significantly change architecture or conventions, update the relevant section here before closing the task.

## Commands

```bash
# Run the full pipeline
uv run --frozen python -m main <input.epub> [--num-cards 15] [--card-size A6] [--resume --output-dir output/...] [--instructions "..."]

# Run the Streamlit UI (dev mode, includes dev pages)
make dev                  # BB_DEV=1, src/web/app.py on port 9201

# Run the Streamlit UI (prod mode, prod pages only)
make run                  # src/web/app.py on port 9201

# Run type-checking and linting. You should use this frequently as the best way to catch errors early.
make check                # ty check src/ && ruff check src/

# Run tests
make test                 # pytest tests/
```

## Architecture

**Breaking Books v2** turns an EPUB/HTML/Markdown book into a printable flashcard PDF deck using a Claude agent.

### Pipeline (`src/main.py`)

```
load_book(epub)           →  HTML            (cached to OUT/book.html)
run_agent(...)            →  TMP/cards.json  (BBGame JSON, session_id to OUT/session_id.txt)
cards_json_to_pdfs(...)   →  TMP/renders/*.pdf (images on-demand → OUT/images/, fonts cached to data/fonts/)
merge_pdfs_to_print(...)  →  output_dir/deck.pdf
```

Output layout per run: `output/{timestamp}_{random}_{slug}/` with `tmp/` (agent scratch) and `out/` (persistent: versioned snapshots, QC reports, session_id, logs, image cache). Fonts cached globally in `data/fonts/`.

### Agent (`src/agent.py`)

Uses **claude-agent-sdk** (`ClaudeSDKClient`). The agent receives a system prompt (built by `src/big_prompt.py`) with role + card-writing guidelines, the full Google Fonts index, and config. The initial user message contains the card schemas (from `build_schema_docs()`) and the full book HTML in a `<book>` tag.

- Allowed tools: `Read`, `Write`, `Edit`, `Glob`, `mcp__bb__quality_control`
- `permission_mode="acceptEdits"`, `cwd=work_dir.root`, model: `haiku`
- The agent writes `cards.json` directly using file tools, then calls `quality_control()` as an MCP tool
- Resume: session_id stored in `OUT/session_id.txt`, passed as `ClaudeAgentOptions(resume=session_id)`

### Agent prompt structure (`src/big_prompt.py`)

The prompt instructs the agent to work in four phases:
1. **Map the book** — decide sections, identify card candidates, plan cross-reference chains, sketch narrative paths; write to `book_plan`
2. **Visual identity** — choose two Google Fonts (title/body) and one `SectionTheme` (main/dark/accent hex colors) per section
3. **Write cards** — produce the full `cards` array in one shot, then iterate via QC
4. **Quality control** — call `quality_control()` up to `max_qc_calls` times

### Quality control (`src/tools/quality_control.py`)

The QC tool runs three checks and returns a natural-language report:
1. **JSON structure** — validates `BBGame` + each `Card` against Pydantic schemas
2. **Section balance** — checks card count vs target (±30%), section distribution, and that `section_themes` count == number of unique sections
3. **LLM review** — calls Cerebras (`gpt-oss-120b`) to review language consistency, undefined terms, and image description style; returns a verdict of "All good" / "Nit" / "Changes requested"

Saves versioned snapshots: `OUT/cards-vNNN.json` + `OUT/qc-report-vNNN.md`.

### Data model (`src/lib/models.py`)

```
BBGame
├── book_plan: str
├── visual_identity: VisualIdentity
│   ├── description: str
│   ├── title_font: str
│   ├── body_font: str
│   └── section_themes: list[SectionTheme]   # one per section, in order
│       ├── main_color: str   # hex
│       ├── dark_color: str   # hex
│       └── accent_color: str # hex
└── cards: list[Card]          # discriminated union, field: "type"
```

`Schema` base fields (all cards inherit these): `type` (Literal), `section` (int, 0-based), `tag` (optional: `"top_end"` / `"middle"` / `"bottom_end"` for grouped card sequences).

### Schemas (`src/schemas/`)

Each card type is a `Schema` subclass in its own file. The `Card` discriminated union in `src/schemas/__init__.py` must be updated when adding a new type. `src/lib/registry.py` auto-discovers schema classes and templates via `pkgutil`—no manual registration needed beyond updating the union.

Current card types: `Axis`, `DefaultCard`, `Definition`, `Diagram`, `Enumeration`, `ExampleCard`, `LongQuote`, `Question`, `SectionCard`.

### Templates (`src/templates/`)

Jinja2 + WeasyPrint HTML templates that render cards to PDF. Each schema class declares valid templates via a glob pattern `templates: ClassVar[str]` (e.g., `"default-*.html.jinja2"`). At render time one matching template is chosen at random (or `card["template"]` overrides).

**Template variables**:
- All card fields such as `section`, `tag`, (from `src/schemas/_base.py:Schema`), and the card-specific fields `title`, `description`, etc, defined in their respective `src/schemas/{card_type}.py` file.
- `visual_identity`: a dict with `title_font`, `body_font`, `description`, and `section_themes` (list of dicts with `main_color`, `dark_color`, `accent_color`). Defined in `src/lib/models.py:VisualIdentity`.
- `get_image(prompt, width, height)`: callable returning base64 PNG data URI (generated by Runware API, cached to `OUT/images/{sha256(prompt+size)}.png`).

**Size**: All templates render at A6 (210 × 148 mm). Scaling for larger formats happens at PDF merge stage.

### Adding a new card type

1. Create `src/schemas/{name}.py` — subclass `Schema`, set `type: Literal["new-type"]`, declare `templates: ClassVar[str]` with a glob pattern (e.g., `"my-type-*.html.jinja2"`), override `get_examples()` with at least one example instance
2. Add the new class to the `Card` union in `src/schemas/__init__.py`
3. Add matching template(s) to `src/templates/{name}-*.html.jinja2`
4. Registry and agent prompt (`build_schema_docs()`) update automatically
5. Update this file

### Adding a new template

1. **File location**: Create a Jinja2 template in `src/templates/{card_type}-{variant}.html.jinja2`
   - Naming: `{card_type}` matches the schema type (e.g. `default`, `question`, `definition`)
   - Example: `default-classic.html.jinja2`, `question-mcq.html.jinja2`

2. **Page size**: All cards render at **A6 size** (210 × 148 mm, portrait)
   - Set `@page { size: A6 portrait; margin: 0; }` in template CSS
   - Scaling for larger formats (A5, etc.) happens at the PDF merge stage, not during template rendering

3. **Template variables**:
   - `card`: all fields from the Card schema (e.g. `title`, `description`, `question`, `options`, `answer`)
   - `visual_identity`: dict with:
     - `title_font`: font name string (e.g. `"EB Garamond"`)
     - `body_font`: font name string (e.g. `"Lora"`)
     - `description`: visual identity description string
     - `section_themes`: list of dicts, each with `main_color`, `dark_color`, `accent_color` (hex strings)
   - `get_image(prompt, width=768, height=512)`: callable that returns base64 PNG data URI (or None if generation fails)

4. **Fonts**:
   - Use `visual_identity.title_font` and `visual_identity.body_font` in CSS
   - Font cache (`src/lib/font_cache.py`): `fetch_and_cache_css(url)` fetches CSS and font files, caches in `data/fonts/` (CSS in `data/fonts/css/`, fonts as `{hash}.{ext}`). Supports .woff2, .woff, .ttf, .otf. Idempotent. `fetch_and_cache_fonts` (Google) and `fetch_and_cache_font_awesome` are thin wrappers. Templates receive `font_face_css` and `font_awesome_css` with local `@font-face` rules.
   - Always include fallback fonts: `font-family: {% if visual_identity.title_font %}'{{ visual_identity.title_font }}', {% endif %}'EB Garamond', serif;`
   - The agent chooses Google Fonts that are available; template ensures graceful fallback

5. **Colors**:
   - `visual_identity.section_themes` contains exactly **one** theme (the card's own section). Always use index `[0]`.
   - `main_color` = section background tint (often light), `dark_color` = dark foreground / band bg, `accent_color` = vivid highlight
   - Shared pattern: card bg = `main_color`, top band bg = `dark_color`, border = `accent_color`

6. **Images**:
   - Both `width` and `height` must be multiples of 64.
   - Call from template: `{% set img = get_image("prompt text", width, height) %}`
   - Returns raw base64 string or None. Render as: `<img src="data:image/png;base64,{{ img }}">`
   - For CSS background: `background-image: url('data:image/png;base64,{{ img }}');`

7. **Shared macros** (`_card_base.html.jinja2`):
   - Import: `{% from '_card_base.html.jinja2' import type_icon_class, tag_class, top_band_html, css_imports, shared_css %}`
   - `css_imports(font_face_css, font_awesome_css)` — both passed from render_card_to_pdf (which fetches and caches them from visual_identity)
   - `shared_css(visual_identity, theme)` — base CSS: `@page`, border, top band, title, `<b>` underline
   - `top_band_html(type, section)` — renders the 9mm dark band with section label + type icon
   - `tag_class(tag)` — returns CSS class string (` tag-top`, ` tag-middle`, ` tag-bottom`, or empty)
   - Border tag system: `.tag-top` removes bottom border, `.tag-middle` removes top+bottom, `.tag-bottom` removes top

8. **Card design system**:
   - Top band (9mm, `dark_color` bg) always present, always contains: `§N` section label + FA type icon in `accent_color`
   - Border: 2pt solid `accent_color` around entire card; tag removes one or two sides to group cards visually
   - `definition-lexicon` is the exception: left spine instead of top band (rotated icon + section label)
   - FA icons by type: default=fa-lightbulb, section=fa-bookmark, question=fa-circle-question, long_quote=fa-quote-left, definition=fa-book, enumeration=fa-list-ol, diagram=fa-diagram-project, example=fa-flask, axis=fa-sliders

9. **Register template**:
   - The schema's `templates: ClassVar[str]` uses a glob pattern to match templates automatically
   - Files starting with `_` (like `_card_base.html.jinja2`) are not picked up by any schema glob

8. **Test without LLM**:
   - Use `uv run pytest tests/test_render_templates.py` (no LLM required)
   - Importantly, this shows any warnings from WeasyPrint. Those should be fixed as they likely correspond to features that are not supported by WeasyPrint.
   - Streamlit: `make dev` → select "Render Templates" page → choose visual identity style

### Tests (`tests/`)

Run with `make test`. The command first runs `ty` type-checking and `ruff` linting, then runs the tests. Add a quick test when adding new code.

A lot of files can also be run as CLI scripts for smoke testing and checking quality. You should run them when modifying corresponding code.

### Web UI (`src/web/`)

Streamlit app with two modes:
- **Prod** (`make run`): shows `prod_pages/` only — Generator + Render Deck
- **Dev** (`make dev`, `BB_DEV=1`): also shows `dev_pages/` — pipeline inspection tools (extract, schema docs, render templates, PDF→PNGs, merge PDFs, QC, card generator)

Structure:
```
src/web/
├── app.py              # entrypoint; st.navigation() controls which pages appear
├── prod_pages/
│   ├── 1_Generator.py  # main UI: upload book → run agent → view deck
│   └── 2_Render_Deck.py
└── dev_pages/
    ├── 1_Extract.py
    ├── 2_Build_Schema_Docs.py
    ├── 2_Render_Templates.py
    ├── 3_PDF_to_PNGs.py
    ├── 4_Merge_PDFs.py
    ├── 5_Quality_Control.py
    ├── 6_Card_Generator.py
    └── 7_Agent_Log.py
```

When adding new pages, update the `st.navigation()` call in `src/web/app.py`.


### Other notes
- Always run `make check` before considering your work complete.
- Always update this `CLAUDE.md` when making code changes. Consider `CLAUDE.md` as living documentation that needs to be kept up to date. If you notice `CLAUDE.md` is outdated, update it.
