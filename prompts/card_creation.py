
create_cards_declaration = {
    "name": "create_cards",
    "description": "Generates a set of formatted Zettelkasten cards from the provided card definitions.",
    "parameters": {
        "type": "object",
        "properties": {
            "card_definitions": {
                "type": "array",
                "description": "Array of card definitions",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Concise title that captures the core idea of the card in a few words."
                        },
                        "description": {
                            "type": "string",
                            "description": "Concise explanation of the idea (~ 3 sentences)."
                        },
                        "illustration": {
                            "type": "string",
                            "description": "Detailed description of a visual that represents the idea (without any text elements). Be creative and imaginative: if the idea is visual in nature, simply translate it into a clear scene, else you can use precise visual metaphor to illustrate an idea that is too abstract."
                        },
                        "quotes": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Set of 1-5 direct quotes from the book where the idea appear"
                        },
                    },
                    "required": ["title", "description", "quotes", "illustration"]
                }
            },
        },
        "required": ["card_definitions"]
    }
}


CARD_EXTRACTION_PROMPT = """
# Instruction
You are reading a long section of a book. You role is to create {NB_CARD} Zettelkasten cards containing the key ideas from the content of this section. Every cards has a title, a description, an illustration and an ensemble of quotes containing, supporting or embodying the idea. 

Ensure the cards cover _all_ the content from this section. If I were to use the cards in a slide show to present the section to an audience, I could use the cards as a slide show to tell the complete story of the section without loosing much details.

## Guidelines:
1. Each card should represent ONE distinct, atomic idea from the text
2. Ensure cards collectively cover the COMPLETE content of the section
3. Use clear, precise language in the descriptions. Make use of bold HTML <b> tag for emphasis.
4. Create simple, precise descriptions of PHOTOGRAPHIC illustration that gives understanding of the idea at first glance.
5. The illustration should be of a scene or a situation that is representative of the idea, there should be NO LABEL, NO DIAGRAM and NO TEXT
6. Extract 1 to 5 direct quotes that best exemplify each idea. Ensure quotes are full sentences that can be read as stand alone.
7. Include ideas that are not directly named in the text but are present, scattered or diffused accross the text
8. Include counterintuitive or surprising elements when present in the text

## Output Format:
The cards should be usable as:
- A standalone reference to an idea
- A sequential slide deck that tells the full narrative of the section
- A network of interconnected ideas that maintains the author's original meaning

# Book section

{BOOK_SECTION}

"""


STYLE_PROMPT = """
# Instruction
Your goal is to select the perfect visual style for each card illustration in a unified deck while maintaining cohesive design language. Each recommended style should:

1. Stay close to the style keywords from the list below
2. Return a list of {NB_CARD} styles, one for each card
3. Focus on pure style instructions, nothing related to the content of the picture

# Examples styles keywords:

### Art Movements
Impressionism
Expressionism
Surrealism
Cubism
Art Deco
Art Nouveau
Baroque
Renaissance
Pop Art
Minimalism
Abstract Expressionism
Pointillism
Fauvism
Futurism
Dadaism
### Digital Art Styles
Pixel art
Vaporwave
Glitch art
Low poly
Isometric
Cyberpunk
Synthwave
### Digital painting
3D rendering
Holographic
Traditional Media
Watercolor
Oil painting
Charcoal sketch
Pencil drawing
Ink illustration
Acrylic painting
Pastel
Gouache
Woodcut
Linocut
Collage
Screen printing
### Photography Styles
Long exposure
Macro photography
Aerial photography
Black and white
Bokeh
HDR
Film grain
Polaroid
Vintage photography
Tilt-shift
### Lighting & Mood
Golden hour
Blue hour
Dramatic lighting
Cinematic lighting
Chiaroscuro
Noir
Ethereal
Dreamy
Moody
High-key
Low-key
### Visual Aesthetics
Cottagecore
Dark academia
Steampunk
Solarpunk
Dieselpunk
Atompunk
Kawaii
Brutalist
Gothic
Retro-futurism
### Artist References
"in the style of [artist name]" (e.g., Salvador Dalí, Claude Monet, etc.)
Studio Ghibli style
Disney style
Marvel/comic book style
Ukiyo-e (Japanese woodblock prints)
Specific Renderers
Unreal Engine
Cinema 4D
Octane render
V-ray
Blender
Zbrush

# Cards

{CARDS}

"""