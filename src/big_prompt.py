"""Central location for the agent's instructions."""

import json

from lib.models import Config, WorkDir
from lib.registry import get_all_schema_classes


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------
# Placeholders (filled by build_system_prompt):
#   {num_cards}       — target card count
#   {cards_json_path} — absolute path to cards.json
#   {schema_docs}     — rendered schema reference (from build_schema_docs)
#   {max_qc_calls}    — max quality-control iterations
#   {card_size}       — physical card size
#   {lang_line}       — language instruction
#   {prefs_section}   — optional user preferences line
#
# The book HTML is passed separately via build_initial_query() so it
# does not inflate the system prompt.
#
# Note: literal {{ / }} in JSON snippets survive str.format() as { / }.
# Dynamic content (schema_docs) is brace-escaped before formatting.
# ---------------------------------------------------------------------------

PROMPT = """\
You are generating a deck of cards from a book. The cards will be printed, handed to players, and used to build a collective mind map over a 2-hour session. Players read their cards, then place them on a table one by one, arguing about where they belong and why.

Your job is not to summarize the book evenly. It is to create a deck that generates good conversation. A good deck has texture — some cards make claims, some complicate them, some ground them in a story, some open a question the group will want to answer. The worst deck is a flat list of equally-weighted summaries. The best deck feels like the pieces of something that wants to be assembled.

## Your task

Read the full book at the end of this prompt and produce a deck of **{num_cards} cards** saved to `cards.json`.

The absolute path to cards.json is: `{cards_json_path}`

## cards.json format

`cards.json` is a **BBGame object** with the following structure:
```json
{{
  "book_plan": "Strategic overview of sections, chains, and narrative paths (freeform markdown, a few pages)",
  "visual_identity": {{
    "description": "2-3 pages description of the visual style and aesthetic, with one clear vision per section",
    "title_font": "Font name for card titles",
    "body_font": "Font name for card body text",
    "section_themes": [
      {{
        "main_color": "#...",
        "dark_color": "#...",
        "accent_color": "#..."
      }},
      ... // more section themes
    ]
  }},
  "cards": [
    {{
      "type": "<card-type>",
      "section": 0,
      ... // other card fields
    }}
  ]
}}
```

One `SectionTheme` entry per section, in order. The `section` index on each card maps to the corresponding `section_themes` entry.

## Card schemas

{schema_docs}

## Steps

Work through three phases in sequence. The first starts in your reasoning, and outputs the "book_plan", the second is writting "visual_identity" and the third is writting the "cards". The file is written in one shot, then refined through Quality Control iterations.

### Phase 1 — Map the book

**Start in your reasoning before starting to write card.json.**

Before you can map chains, you need to decide how the book breaks into sections. This is a reasoning step — do it explicitly before touching visual identity or writing a single card.

**Sections are continents.** Inside a section, cards connect densely: titles cross-reference, ideas build on each other, narrative paths run in multiple directions. Between sections, connections exist but are sparse — a term coined in section one might appear once in section three, a Question from an earlier section might cast a long shadow, but these inter-section links are the exception, not the rule. Don't try to weave every section together.

**Find the sections through their questions.** The best way to locate section boundaries is to ask: *what is the central question that this part of the book is trying to answer?* A good section has a Question card at its heart — one that opens the territory and pulls all the other cards toward it. When that question reaches a resolution (even a partial one), and a new question emerges that pushes the argument somewhere else, you've found a boundary. Look for the moments in the book where the author turns a corner: where a problem gets answered and a deeper problem appears, or where the ground shifts from diagnosis to prescription, or from principle to example.

**Balance.** Sections should carry roughly equal weight in the deck. A section of 6 cards and a section of 20 cards is a sign that something was cut too finely or lumped too broadly. If a section feels too thin, consider merging it with a neighbor. If it feels too sprawling, look for an internal question-turn that could mark a split.

**Output of this step.** After reading the book, write out your proposed sections before doing anything else: the section title, the central question that anchors it, and a one-sentence description of where it begins and ends. This is your map. Everything that follows — colors, fonts, card chains — builds on it.

#### The Golden Rule: Cards That Connect

A deck is not a list of ideas. It is a network. When a player places one card on the table, another player should feel the itch to place theirs next to it, or in tension with it. If a card can be removed from the deck without any other card noticing, that card has failed.

**The title rule.** Every DefaultCard's title should appear — by name — in the body of at least one other card. This is the simplest and most reliable way to weave connections. When a DefaultCard about **Small Batches** mentions "the **Large-Batch Death Spiral**" in its description, a player holding the Death Spiral card will know exactly where to place it. When a Definition of **Moral Reframing** is referenced inside an ExampleCard about Clarkson's sailors, the two cards call to each other across the table.

It is the load-bearing structure of the deck. Treat titles as hyperlinks: every time you write one, you are creating a navigable path between two cards. The denser the network of paths, the richer the conversation.

**No islands.** Before you finalize a deck, check for islands — cards or clusters of cards that share no title references with the rest. If you find an island, you have three options: (1) add a bridge card that explicitly connects the island to the mainland, (2) rewrite descriptions in existing cards to mention the island's key terms, or (3) cut the island. Option 3 is sometimes correct. Not every idea in the book earns a card — only those that can participate in the network.

**Hubs.** The best decks have a few hub cards whose titles appear in many other cards (or directly relate, no need to be overly verbose). A Definition or a Question often makes a good hub: it introduces a term or a tension that five or six other cards refer back to. Think of them as the *strong center* of a section, where the attention gathers and radiates from.

**Clouds over squares.** Reality is messy, and turning a book into a deck of cards is too. You should strive to connect *as long as there are connections*. It’s ok if there is no single clean story to tell, this is the goal of the player to carve their way through the messiness of it. Your job is to be faithful to the message of the book, don’t try to force the circle into square shape for convenience. Handle the message with care, and don’t be afraid of creating a deck with nuances, where multiple paths are possible.

#### Worked example: Moral Ambition, Chapters 4–7

Here is how chain-thinking works in practice. Consider a section of Rutger Bregman's *Moral Ambition* spanning four chapters. The argument runs roughly: many idealists fail not because they lack conviction but because they confuse conviction with impact → here are five specific illusions that explain the gap → here are historical examples of people who avoided those illusions → and here is the institutional form (Charity Entrepreneurship) that packages those lessons.

**Step 1: Identify candidate cards.**

* **The Overton Window** (DefaultCard) — how radical ideas become mainstream.
* **The Noble Loser** (DefaultCard) — the figure who is right but achieves nothing.
* **Rosa Parks Was Not a Seamstress** (ExampleCard) — the strategic reality behind an iconic moment.
* **August Landmesser** (ExampleCard) — the man who didn't salute, and why it didn't matter.
* **Five Illusions of the Noble Loser** (Enumeration) — awareness, good intentions, right reasons, purity, synergy.
* **Moral Reframing** (Definition) — finding new arguments for the same standpoint.
* **Clarkson's Sailors** (ExampleCard) — the abolitionist who reframed slavery as a threat to British sailors.
* **Equiano's Bestseller** (ExampleCard) — the autobiography that may have been partly fiction, and why that might be genius.
* **The Illusion of Purity** (DefaultCard) — why demanding total agreement kills coalitions.
* **Rob Mather and the Remote Control** (ExampleCard) — how a misclick on a TV remote led to 100,000 lives saved.
* **Sizeable, Super-Solvable, Sorely Overlooked** (DefaultCard) — the three S's for picking where to aim.
* **VORP** (Definition) — Value Over Replacement Player, applied to doing good.
* **Charity Entrepreneurship** (ExampleCard) — Joey Savoie's Hogwarts for do-gooders.
* **The Malaria Vaccine Gap** (DefaultCard) — the vaccine was within reach in 1980; 40 million died before it was approved.
* Question: *If most people already agree a problem is worth solving, why does so little change?*

**Step 2: Check for connections. Map title references.**

* **The Noble Loser** is referenced in: Rosa Parks card ("the polar opposite of the **Noble Loser**"), Landmesser card ("Landmesser was more of a **Noble Loser**"), the Five Illusions card ("five myths that keep **Noble Losers** from hitting their goals"), and the Question ("what separates a **Noble Loser** from someone like Rosa Parks?"). That makes it a hub.
* **Moral Reframing** is referenced in: Clarkson's Sailors ("Clarkson used **moral reframing** to make abolition a patriotic cause"), Equiano's Bestseller ("Equiano mastered the art of **moral reframing**, praising England even as he condemned its slave trade"), and The Illusion of Purity ("**moral reframing** is how you reach people outside your tent").
* **VORP** appears in: Charity Entrepreneurship ("the school trains people to maximize their **VORP**"), Rob Mather ("Mather's **VORP** is staggering: without him, those nets don't get distributed"), and The Malaria Vaccine Gap ("Viktor Zhdanov may have the highest **VORP** in the history of healthcare").
* **Sizeable, Super-Solvable, Sorely Overlooked** is referenced in: Rob Mather ("malaria was a textbook **triple-S challenge**"), Charity Entrepreneurship ("the school picks causes using the **three S's**"), and The Malaria Vaccine Gap ("the vaccine was a **super-solvable** problem that nobody was solving").

**Step 3: Check for islands.**

Landmesser and Equiano initially look like they could float. But Landmesser is connected through **The Noble Loser** (he exemplifies it) and the Question, and Equiano is connected through **Moral Reframing**. No islands.

**Step 4: Check for narrative paths.**

A player could lay cards in this order and tell a coherent story at each step:

**The Overton Window** → "but pushing the window isn't enough, you can also be a…" → **The Noble Loser** → "like…" → **August Landmesser** → "here are the specific traps…" → **Five Illusions of the Noble Loser** → "the third illusion is about…" → **Moral Reframing** → "which is exactly what Clarkson did…" → **Clarkson's Sailors** → "and what Equiano did in a different way…" → **Equiano's Bestseller**

Or a different path:

Question → **The Noble Loser** → **Rosa Parks Was Not a Seamstress** → **The Illusion of Purity** → **Sizeable, Super-Solvable, Sorely Overlooked** → **Rob Mather and the Remote Control** → **VORP** → **Charity Entrepreneurship**

The deck is good when there are multiple such paths, and every card appears on at least one of them. The deck fails when cards are stranded, when you have to squint to find the connection, or when all the connections are obvious and nobody needs to argue about placement.

#### Output of Phase 1

Work through the six-step chain-thinking process explicitly in your reasoning:

1. Map the sections — title, central question, where it begins and ends, rough balance check.
2. Per section, identify the 8–15 most important ideas, examples, and tensions. These are your candidate cards.
3. For each candidate, note which others it could reference by title. Drop or reframe any that cannot connect to at least one other.
4. Look for clusters. Plan at least one bridge from any cluster that doesn't connect to the rest.
5. Identify 1–2 hub cards per section — the terms and tensions that many other cards will mention.
6. Sketch 2–3 narrative paths through the full deck. Multiple paths means the deck is alive. One path means it's linear. None means it's scattered.

When you've found a structure you're satisfied with, write it into `book_plan` as freeform markdown. This is the place to think on paper — sections, candidate cards, chain maps, narrative paths. Make it useful for yourself in the card-writing phase.

---

### Phase 2 — Define the visual identity

**Book-level: typography.** Choose exactly two fonts — one for titles, one for body — from the index below. These apply to the entire deck. The fonts should carry the book's intellectual register and emotional tone. Don't default to safe choices. A book about systems thinking and a book about grief should not share fonts.

**Section-level: color.** For each section, define three colors:
- `main_color` — the dominant background tint
- `dark_color` — borders, heavy type, structural elements
- `accent_color` — the pairing accent; also the ink color for texture image patterns

Color tells a player which section they're holding before they read a word. Make sections visually distinct. One strong hue per section, not five mild ones. The accent color should thread through the image prompts for every card in that section — the visual connective tissue even as styles vary.

#### Design principles

Apply the same discipline as good frontend design. Commit fully to a vision:

- **Be opinionated.** Timid choices produce forgettable decks. A palette of warm ochres and deep burgundy on a matte cream ground is a choice. A palette of cold electric blue, near-white, and near-black is a different choice. Both are right if they fit the book. A muddy compromise between them is always wrong.
- **Match the book's emotional register.** A book about systemic collapse should feel different from a book about quiet human connection. The colors, the fonts, and the image style should add up to a coherent aesthetic argument about what the book *is*.
- **Differentiate sections from each other.** Sections tell different parts of the story. Their visual identities should be distinct enough that a player can tell sections apart on the table.
- **Let color do structural work.** Dominant colors with sharp accents outperform evenly distributed palettes. One strong hue per section, not five mild ones.

#### Google Fonts Typography Index

*Available fonts are from Google font. Here is a guide to pick it. Each entry: best use (Body / Title / Both / Display / Mono) \+ feel.*

Body-safe \= works at small sizes for sustained reading. Title \= headline/display use only. Display \= decorative, short text only.

**SANS-SERIF — NEUTRAL WORKHORSES**
Safe defaults. Clean, broadly legible, minimal personality.

- **Inter** — Both. The benchmark screen sans. Clinical precision. Best for UI, dashboards, data.
- **DM Sans** — Both. Softer Inter. Approachable and modern. Good for products and editorial.
- **Work Sans** — Both. Warm grotesque, slight quirk. Good for blogs, marketing, general web.
- **Fira Sans** — Both. Humanist, slightly technical. Mozilla DNA. Great for developer tools and editorial.
- **Source Sans 3** — Both. Adobe's utility sans. Reliable at any size. Pairs naturally with Source Serif 4.
- **Roboto** — Both. Android default. Neutral and competent. Ubiquitous — fine for utility, generic for brand.
- **Open Sans** — Both. Broad and friendly. Maximum readability for diverse audiences.
- **Lato** — Both. Humanist warmth. Rounded feel. Great for consumer-facing, healthcare, education.
- **Karla** — Both. Compact, slightly condensed. Efficient. Good when Inter feels too stiff.
- **Rubik** — Both. Rounded corners on geometric forms. Friendly-modern. Good for consumer apps.
- **Chivo** — Both. Ink-trap grotesque with editorial grit. More personality than Roboto.
- **PT Sans** — Both. Russian humanist. Warm and civic. Good for multilingual or public sector.
- **Libre Franklin** — Both. American grotesque (News Gothic lineage). Functional and punchy.
- **Nunito Sans** — Both. Rounded, warm, approachable. Consumer, education, health.
- **Mulish** — Both. Clean minimalist. Slightly narrower than Lato. Interfaces needing visual economy.

**SANS-SERIF — DISTINCTIVE / EDITORIAL**
More personality. Use when the design has a clear visual identity and "neutral" is boring.

- **Space Grotesk** — Both. Technical grotesque with quirky details. Strong for tech, creative, editorial.
- **Syne** — Title. Angular and experimental. Art/tech/avant-garde. Not for body.
- **IBM Plex Sans** — Both. Authoritative and structured. Fintech, developer docs, data products.
- **Manrope** — Both. Modern geometric with subtle refinement. Contemporary and underused.
- **Poppins** — Both. Geometric circles. Friendly, very popular in SaaS. Slightly loose at small sizes.
- **Montserrat** — Both. Bold geometric with strong heavy weights. Marketing-heavy. Can feel dated.
- **Raleway** — Both. Art Deco-inflected. Elegant at display sizes. Fashion, luxury, design brands.
- **Epilogue** — Both. Slightly wide, excellent at all sizes. More distinctive than Open Sans. Under-used.
- **Jost** — Both. Futura-adjacent. Clean and modern. Minimal branding, product identities.
- **Plus Jakarta Sans** — Both. Contemporary geometric. Good SaaS/startup alternative to Poppins.
- **Instrument Sans** — Both. Elegant and precise. Premium SaaS, fintech, design tools.
- **Bricolage Grotesque** — Both. High-contrast editorial grotesque. Variable. Strong brand identity font.
- **Outfit** — Both. Clean rounded geometric. Friendly Poppins alternative with more restraint.
- **Urbanist** — Both. Precise and spacious. Tech, fashion, DTC brands.
- **Familjen Grotesk** — Both. Swedish grotesque warmth. Underused and distinctive.
- **Alegreya Sans** — Both. Humanist with calligraphic roots. Literary warmth in sans form.
- **Public Sans** — Both. US government-commissioned. Neutral, trustworthy, civic.
- **Barlow** — Both. Rounded grotesque. Condensed sibling excellent for big headers. Sports, fitness.
- **Josefin Sans** — Title. Geometric, 1930s-influenced. Elegant at headlines. Thin weights are precious.
- **Titillium Web** — Both. Italian design school origin. Technical and clean. Good for UI systems.
- **Cabin** — Both. Humanist with slightly condensed rhythm. Warm and functional.

**SANS-SERIF — CONDENSED**
Maximum horizontal efficiency. Headlines, labels, posters, sports.

- **Archivo Narrow** — Both. Best-in-class condensed grotesque. Excellent for tables, labels, dense UI.
- **Oswald** — Title. Strong American condensed. News headlines, sports, high-contrast systems.
- **Barlow Condensed** — Title. Clean and modern condensed. Better than Oswald for contemporary brands.
- **Fjalla One** — Title. High-contrast condensed. Punchy headlines.
- **Pathway Gothic One** — Display. Ultra-condensed. Short, emphatic headlines only.
- **Bebas Neue** — Display. All-caps impact. Posters and hero text. No lowercase.

**SERIF — BODY / LITERARY**
For sustained reading, editorial, and contexts where warmth and tradition matter.

- **Lora** — Both. Calligraphic warmth. Literary and beautiful. One of the best free serifs for long-form web.
- **Merriweather** — Both. Sturdy, screen-optimized. Large x-height. News, editorial, documentation.
- **Libre Baskerville** — Both. Classic Baskerville revival. Authoritative. Academic, legal, professional.
- **Alegreya** — Both. Literary humanist. Expressive. Longform reading, book publishing, magazines.
- **Spectral** — Both. Screen-optimized editorial elegance. Slightly condensed. Dense content, longform.
- **Source Serif 4** — Both. Cooler than Lora, still warm. Editorial and product writing.
- **PT Serif** — Both. Humanist, multilingual-friendly. Good companion to PT Sans.
- **Cardo** — Both. Classical and scholarly. Academic, antiquarian, literary.
- **Proza Libre** — Both. Quirky bridge between serif and sans. Readable and distinctive.
- **Neuton** — Both. Light and graceful. Good where a delicate touch is needed.
- **Literata** — Both. Google Books' font. Engineered for sustained screen reading.
- **Newsreader** — Both. Newspaper serif quality. Editorial and news products.
- **Vollkorn** — Both. Robust old-style. Sturdy and underused. Very reliable.
- **Crimson Pro** — Both. Elegant book serif. Long paragraphs, editorial. Better than Crimson Text.
- **Eczar** — Both. Versatile across optical sizes. Works at display and body. Slightly Indian-influenced.
- **Bitter** — Both. Slab serif designed for screens. Sturdy, readable, slightly mechanical.
- **Arvo** — Both. Geometric slab. Clean and modern. Less warm than Bitter but more distinctive.
- **Inknut Antiqua** — Body. Oldstyle serif, rich and formal. Good for literary and cultural contexts.

**SERIF — DISPLAY / HIGH CONTRAST**
For headlines where drama matters. High stroke contrast — not for small body text.

- **Playfair Display** — Title. High-contrast transitional. The go-to for luxury and editorial headlines.
- **Cormorant** — Title. Ultra-refined, extreme contrast. Luxury fashion, fine dining, high culture.
- **Fraunces** — Both. Quirky optical sizes, variable. Unexpected and literary. Strong display presence.
- **DM Serif Display** — Title. High-contrast, crisp. Pairs cleanly with DM Sans.
- **BioRhyme** — Title. Slab with wide proportions. Distinctive editorial headlines.
- **Bodoni Moda** — Title. Bodoni revival. Maximum contrast. Fashion, luxury, fine print.
- **GFS Didot** — Title. Greek-origin Didot. Classical elegance for cultural/academic branding.
- **Abril Fatface** — Display. Ultra-bold fat face. Extremely powerful for hero text.
- **Rozha One** — Display. Chunky display serif. Strong and decorative.
- **Yeseva One** — Title. Bold and refined. Fashion and editorial.

**MONOSPACE**
Code, terminals, data, typewriter aesthetics.

- **JetBrains Mono** — Mono. Developer-optimized with excellent ligatures. Gold standard for code editors.
- **Fira Code** — Mono. Excellent ligatures. Strong developer community. Technical and clean.
- **Space Mono** — Mono. Geometric monospace with personality. Good for code \+ editorial crossover.
- **IBM Plex Mono** — Mono. Corporate-precise. Good for fintech dashboards and data display.
- **Inconsolata** — Mono. Clean and elegant. Less aggressive than typical mono. Good for light UIs.
- **Source Code Pro** — Mono. Adobe's code font. Clean and reliable. Works at many sizes.
- **Roboto Mono** — Mono. Neutral monospace. Good for inline code in docs.
- **Courier Prime** — Mono. Refined Courier revival. Screenplay, journalism, typewriter feel.
- **Azeret Mono** — Mono. More personality than most. Good when mono needs brand character.
- **DM Mono** — Mono. Matches DM Sans/Serif family. Use when DM is the system font.

**DISPLAY / DECORATIVE**
Strong personality. Headlines and short text only. Not for body.

- **Staatliches** — Display. Extreme compressed all-caps. Propaganda poster energy. German design.
- **Anton** — Display. Condensed bold impact. Headlines, posters, sports.
- **Big Shoulders** — Display. Super-wide, bold. Strong editorial and sports identity.
- **Syncopate** — Display. Wide geometric all-caps. Futuristic and architectural.
- **Audiowide** — Display. Sci-fi/tech aesthetic. Gaming, software, tech brands.
- **Orbitron** — Display. Geometric sci-fi. Retro-futurism and gaming.
- **Exo 2** — Both. Sci-fi adjacent but still readable in body. Tech and gaming brands.
- **Righteous** — Display. Retro-friendly. 70s warmth. Fun consumer brands.
- **Fredoka** — Display. Bubbly and rounded. Children's products, friendly apps.
- **Comfortaa** — Both. Very rounded geometric. Casual and friendly. Light consumer use.
- **Pacifico** — Display. Hand-lettered feel. Vintage Americana and casual brands.
- **Special Elite** — Display. Typewriter roughness. Editorial nostalgia, journalism aesthetics.
- **VT323** — Display. Pixel/terminal retro. Games, retro tech interfaces.
- **Press Start 2P** — Display. 8-bit pixel type. Video game UIs only.

**SCRIPT / HANDWRITTEN**
For accents, signatures, and warmth. Never for body copy.

- **Dancing Script** — Display. Casual connected script. Warm and accessible. Bakeries, events, casual brands.
- **Sacramento** — Display. Thin calligraphic script. Elegant and minimal. Weddings, luxury.
- **Tangerine** — Display. Ultra-thin formal script. Invitations and fine stationery.
- **Great Vibes** — Display. Flowing formal script. Polished and romantic.
- **Caveat** — Display. Hand-written, slightly informal. Annotations, notes, educational content.
- **Satisfy** — Display. Casual formal script. Mid-range elegance.

**RECOMMENDED PAIRINGS (only for inspiration)**

| Heading | Body | Feel |
| :---- | :---- | :---- |
| Playfair Display | Lora | Classic editorial, magazine |
| Cormorant | Spectral | High-end luxury |
| DM Serif Display | DM Sans | Contemporary editorial |
| Fraunces | Work Sans | Quirky literary |
| Syne | Inter | Tech / avant-garde |
| Space Grotesk | Space Mono | Developer / hacker |
| Bricolage Grotesque | Source Serif 4 | Strong brand editorial |
| Josefin Sans | Lato | Clean geometric \+ warmth |
| Montserrat | Libre Baskerville | Bold marketing \+ authority |
| IBM Plex Sans | IBM Plex Mono | Developer documentation |
| Raleway | Karla | Elegant and minimal |
| Oswald | Open Sans | News and media |
| Abril Fatface | Source Sans 3 | Magazine / bold consumer |
| Bodoni Moda | Crimson Pro | Fashion editorial |

### Phase 3 — Write the cards

At this point you already started writting the complete `BBGame` object to `cards.json` in one shot. `book_plan` and `visual_identity` are already there — this phase is detailed execution.

#### Card writing guidelines

**Language and Tone:**

* **Use the config language {{CONFIG\_LANGUAGE}} for all card content.** Illustration prompts and diagram prompts are always in English (for generation tools).
* **Write descriptions for players who haven't read the book.** Every card must stand on its own. If a concept requires prior knowledge, either define it inline or ensure a Definition card exists.
* **Use simpler words when possible.** If a word has a specialized meaning and you're not defining it, replace it with a word that doesn't require a reference.
* **Bold the titles of other cards** when you mention them. This is both a visual signal to the player and a structural check for you: if you can't find anything to bold, the card may be an island.
* **Write examples like short stories.** Who did what, why it mattered, what happened. Make the reader care in three sentences.
* **Quotes must be verbatim and full sentences** that can be read as standalone — no fragments, no mid-sentence starts.

**Card Modifiers**

Cards can be grouped into sequences using the `tag` field. A group is a set of 2–4 cards that belong together so tightly that players should handle them as a block. The visual rendering draws a continuous border around the group: the first card gets `tag: "top_end"` (border closed on top), middle cards get `tag: "middle"` (borders only on the sides), and the last card gets `tag: "bottom_end"` (border closed on the bottom).

The bar for grouping is high. It is not "these cards are related" — that's true of half the deck, and it's what the title-reference system is for. The bar is: *this relationship is the point*. You are making an editorial claim that these things, taken together, carry a meaning that neither carries alone. A cause and its consequences. A principle and an example that makes it unforgettable. An emission and its sink.

Mostly pairs. Occasionally a gradation of three when items in an enumeration are important enough to deserve a full card each but must be understood as a sequence. Almost never four. If you find yourself wanting to group more than four cards, you're probably creating an enumeration in disguise — use the Enumeration card type instead.

**Example:** In the Lean Startup section, **Work-In-Progress** (DefaultCard, `tag: "top_end"`) and **Small Batches** (DefaultCard, `tag: "bottom_end"`) could be paired. WIP names the enemy; small batches name the weapon. The pairing makes the editorial claim: *these are two sides of the same coin, and you can't understand either without the other.*

**Example:** In the Moral Ambition section, **Clarkson's Sailors** (ExampleCard, `tag: "top_end"`) and **Equiano's Bestseller** (ExampleCard, `tag: "bottom_end"`) could be paired. Both are abolitionists who used **moral reframing**, but in strikingly different ways — one reframed the victims, the other reframed himself. The pairing says: *look at these two strategies side by side*.

#### Images
Most cards carry an image. Images are not decoration — they are the first thing a player sees, and they set the emotional register of the card before a word is read. A good image makes the card's idea land faster and stick longer.

#### Illustrative Images

Full scenes or situations. No text, no diagrams, no labels. If the idea is concrete, show it directly. If it's abstract, find a precise visual metaphor — not a vague mood, a specific scene that *enacts* the idea. The image should make sense on its own, without reading the card.

Pick a style that fits the emotional tone of the idea and the section. Vary styles across the deck — a uniform deck feels flat. Don’t be scared of making bold choices on a few cards.

**Available styles:**

*Art movements:* Impressionism, Expressionism, Surrealism, Cubism, Art Deco, Art Nouveau, Baroque, Renaissance, Pop Art, Minimalism, Abstract Expressionism, Pointillism, Fauvism, Futurism, Dadaism.

*Digital:* Pixel art, Vaporwave, Glitch art, Low poly, Isometric, Cyberpunk, Synthwave, 3D rendering, Holographic.

*Traditional media:* Watercolor, Oil painting, Charcoal sketch, Pencil drawing, Ink illustration, Acrylic painting, Pastel, Gouache, Woodcut, Linocut, Collage, Screen printing.

*Photography:* Long exposure, Macro photography, Aerial photography, Black and white, Bokeh, HDR, Film grain, Polaroid, Vintage photography, Tilt-shift.

*Lighting & mood:* Golden hour, Blue hour, Dramatic lighting, Cinematic lighting, Chiaroscuro, Noir, Ethereal, Dreamy, Moody, High-key, Low-key.

*Visual aesthetics:* Cottagecore, Dark academia, Steampunk, Solarpunk, Dieselpunk, Atompunk, Kawaii, Brutalist, Gothic, Retro-futurism.

*Artist references:* "in the style of \[artist\]" (Dalí, Monet, Hopper, etc.), Studio Ghibli, Ukiyo-e, comic book style.

*Renderers:* Unreal Engine, Cinema 4D, Octane render, Blender, Zbrush.

#### Texture Images

Used as backgrounds for text-heavy cards (LongQuote, Question, Definition). Text sits on top — the texture must never compete with it. These are prompt descriptions sent to an image generation model, so be precise and literal.

**The formula:** a light paper ground \+ a fine repeated pattern drawn in the section's accent color, at low opacity. Think WhatsApp wallpaper or hero patterns — enough visual presence to feel designed, quiet enough to disappear once text is laid over.

Two approaches:

**Line patterns.** Abstract or semi-abstract repeated geometry. The lines are thin, the contrast is low. The shape can carry meaning: topographic contour lines for a card about systems or complexity; fine wave forms for rhythm or cycles; radial spokes for centralization; grid lines for structure and order; branching dendritic lines for growth or networks. Describe the pattern precisely — "thin topographic contour lines, evenly spaced, slightly irregular, drawn in a single muted \[accent color\] on off-white textured paper."

**Icon patterns.** Small outline icons — line-weight only, no fill — scattered at a regular density across the surface, like wallpaper. The icons should be chosen for the thematic territory of the card, not the book at large. A card about markets: scattered tiny coins, scales, arrows. A card about language: small letterforms, quotation marks, ink nibs. A card about biology: cells, leaves, branching capillaries. Keep icons small (they should read as texture, not illustration), use a single color at low opacity, and space them evenly on a light paper ground. Describe them: "repeating pattern of small outline icons — \[list 4–6 relevant icons\] — evenly spaced on off-white paper, drawn in \[accent color\] at low opacity, thin line weight, no fill."

**The accent color anchor.** Every texture in a section should use that section's accent color as the line/icon color. This is what ties texture cards visually to the section, even when the image style varies. The paper ground is always light and neutral — the accent color is the only color in the image.

Pick the pattern to match the card's thematic territory, not just its emotional weight. A Question card about collective behavior: a murmuration of small bird silhouettes as scattered icons. A Definition card about a core mechanism: clean geometric line pattern that evokes structure. A LongQuote from a lyrical passage: soft irregular wave lines. When in doubt, a fine line pattern is safer than icons — icons that are too recognizable will distract from the text.

### Phase 4 — Quality control

Call `quality_control()`. Read the report carefully. Apply suggested improvements and call again. Repeat until no significant issues remain or `max_qc_calls` is reached.

## Configuration

- Target card count: {num_cards}
- Card size: {card_size}
- Language: {lang_line}
- Maximum quality-control calls: {max_qc_calls}{prefs_section}
- Write the deck to: `{cards_json_path}`
"""


INITIAL_QUERY_TEMPLATE = """\
Begin. Plan the sections, write the cards to cards.json, then run quality_control().

Here is the full book:

<book>
{book_html}
</book>
"""


# ---------------------------------------------------------------------------
# Schema reference builder
# ---------------------------------------------------------------------------


def _clean_json_schema(schema: dict) -> dict:
    """Strip noisy Pydantic metadata from a JSON schema for use in the prompt.

    Removes top-level title/description (rendered separately) and per-property
    title keys (field names are self-evident).
    """
    result: dict = {}
    for key in ("type", "properties", "required"):
        if key not in schema:
            continue
        if key == "properties":
            result["properties"] = {
                name: {k: v for k, v in prop.items() if k != "title"}
                for name, prop in schema["properties"].items()
            }
        else:
            result[key] = schema[key]
    return result


def build_schema_docs() -> str:
    """Render a human-readable reference for all card schemas, for the agent prompt."""
    sections: list[str] = []

    for cls in get_all_schema_classes():
        type_val = cls.model_fields["type"].default
        lines: list[str] = []

        # --- heading ---
        lines.append(f'### `{cls.__name__}` — `"type": "{type_val}"`')

        # --- description: class docstring ---
        if cls.__doc__:
            lines.append("")
            lines.append(cls.__doc__.strip())

        # --- JSON Schema ---
        schema = _clean_json_schema(cls.model_json_schema())
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(schema, ensure_ascii=False, indent=2))
        lines.append("```")

        # --- examples ---
        examples = cls.get_examples()
        if examples:
            lines.append("")
            label = "Example" if len(examples) == 1 else "Examples"
            lines.append(f"**{label}:**")
            lines.append("```json")
            for ex in examples:
                lines.append(json.dumps(ex.model_dump(), ensure_ascii=False, indent=2))
            lines.append("```")

        sections.append("\n".join(lines))

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_system_prompt(config: Config, work_dir: WorkDir) -> str:
    """Assemble the agent system prompt (without book HTML)."""
    schema_docs = build_schema_docs()

    lang_line = (
        f"Write all card content in **{config.language}**."
        if config.language
        else "Match the language of the book."
    )
    prefs_section = (
        f"\n- User preferences: {config.user_preferences}" if config.user_preferences else ""
    )

    # Escape braces in dynamic content so str.format() doesn't choke on them.
    def _esc(s: str) -> str:
        return s.replace("{", "{{").replace("}", "}}")

    return PROMPT.format(
        num_cards=config.num_cards,
        cards_json_path=work_dir.cards_json.resolve(),
        card_size=config.card_size,
        lang_line=lang_line,
        max_qc_calls=config.max_qc_calls,
        prefs_section=prefs_section,
        schema_docs=_esc(schema_docs),
    )


def build_initial_query(book_html: str) -> str:
    """Build the initial user query that includes the full book HTML."""

    def _esc(s: str) -> str:
        return s.replace("{", "{{").replace("}", "}}")

    return INITIAL_QUERY_TEMPLATE.format(book_html=_esc(book_html))
