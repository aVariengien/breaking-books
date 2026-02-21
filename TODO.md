# Breaking Books v2 — Implementation TODO

## Core Models (src/lib/models.py)
- [x] `WorkDir.cards_json` property
- [x] `WorkDir.images_dir` property
- [x] `WorkDir.renders_dir` property
- [x] `WorkDir.create(root)` classmethod
- [x] `OutDir.next_version()`
- [x] `OutDir.cards_json_path(version)`
- [x] `OutDir.qc_report_path(version)`
- [x] `OutDir.create(root)` classmethod
- [x] `OutDir.session_id_path` — for agent resume
- [x] `OutDir.book_html_path` — book HTML cache

## Utilities (src/lib/utils.py)
- [x] `slug(text)` — via python-slugify

## Registry (src/lib/registry.py)
- [x] `get_all_schema_classes()` — auto-discover Schema subclasses
- [x] `get_all_template_paths()` — find all Jinja2 templates
- [x] `get_templates_for_schema(schema_class)`

## Prompt Building (src/big_prompt.py)
- [x] `build_system_prompt(book_html, config)` — assembles full agent system prompt
- [x] Deleted `src/tools/build_agent_prompt.py` (redundant)

## Agent (src/agent.py)
- [x] `run_agent()` — Claude Agent SDK loop with streaming
- [x] `_make_agent_tools()` — quality_control MCP tool via claude-agent-sdk

## Quality Control (src/tools/quality_control.py)
- [ ] `quality_control()` — orchestrate 4-step QC
- [x] `_check_json_structure()` — validate cards.json against schemas
- [ ] `_check_section_balance()` — check for unequal section sizes
- [ ] `_llm_review()` — LLM review of content quality
- [ ] `_visual_review()` — render and vision-check cards

## Content Extraction (src/tools/extract_book_content.py)
- [x] `extract_book_content(epub_path)` — convert EPUB to HTML

## Image Generation (src/tools/generate_images.py)
- [x] `generate_image()` — call Runware API with caching
- [x] `generate_images_for_cards()` — batch generate images

## PDF/PNG Rendering (src/tools/render_template.py, src/tools/pdf_to_pngs.py, src/tools/merge_pdfs.py)
- [ ] `render_card_to_pdf()` — Jinja2 + WeasyPrint single card
- [ ] `cards_json_to_pdfs()` — batch render with parallelization
- [ ] `pdf_to_pngs()` — convert PDF pages to PNG
- [ ] `merge_pdfs_to_print()` — combine cards into printable sheet

## CLI (src/main.py)
- [x] `main()` — orchestrate full pipeline from CLI

## Web UI (src/web.py)
- [ ] `main()` — entry point and phase routing
- [ ] `configure_phase()` — EPUB upload + config
- [ ] `generation_phase()` — stream agent progress
- [ ] `review_phase()` — display results + allow edits

---

## Implementation Notes
- WorkDir = agent's scratch space (TMP/)
- OutDir = versioned snapshots (OUT/)
- Card images cached by SHA256(prompt)
- Agent runs via Anthropic SDK with tool use
- QC saves snapshots after each call
- Templates auto-discovered from src/templates/
