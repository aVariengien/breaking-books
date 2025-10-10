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
                            "description": "Concise title that captures the core idea of the card in a few words.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Concise explanation of the idea (~ 3 sentences).",
                        },
                        "illustration": {
                            "type": "string",
                            "description": "Detailed description of a visual that represents the idea (without any text elements). Be creative and imaginative: if the idea is visual in nature, simply translate it into a clear scene, else you can use precise visual metaphor to illustrate an idea that is too abstract.",
                        },
                        "quotes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Set of 1-5 direct quotes from the book where the idea appear",
                        },
                    },
                    "required": ["title", "description", "quotes", "illustration"],
                },
            },
        },
        "required": ["card_definitions"],
    },
}


MAXI_PROMPT = """You are a literary analyst with expertise in organizing complex texts into 3 meaningful logical sections based on thematic elements, narrative arcs, or major plot developments. I need you to analyze the book I provide and break it down into coherent thematic sections.

The book is in html format with html tags marked by tag ids (e.g. id="tag-230") that marks the position in the text. You will be asked to give these tag values to mark the end and the beginning of a section or excerpt.

Important guidelines:
* ! Use the language of the book for all your responses, e.g. if the book is in French, use French for all your responses.
* Extract VERBATIM quotes for all passages, excerpts, and key quotes
* Use mardown formatting to add emphasis like bold and italic to the section descriptions
* Choose section colors that align with the emotional tone or themes. Make sure the colors are contrasting and not too similar to each other.
* Include 1-3 key passages that are around half a page long that best represent the section's themes
* Your landscape descriptions should always be in English. It should be detailed and evocative, capturing the section's emotional essence
* Identify 1-3 key quotes per chapter that highlight important moments, revelations, or character development
* Make sure section introductions clearly articulate the thematic questions being explored and how they connect to previous sections
* Please maintain the exact JSON structure provided. This analysis will be used for creating a visual and thematic guide to the book.

# Book

{BOOK}"""

CARD_EXTRACTION_PROMPT = """
# Instruction
You are reading a long section of a book. You role is to create {NB_CARD} Zettelkasten cards using HTML formatting containing the key ideas from the content of this section. Every cards has a title, a description, a type, an illustration and an ensemble of quotes containing, supporting or embodying the idea.

Ensure the cards cover _all_ the content from this section. If I were to use the cards in a slide show to present the section to an audience, I could use the cards as a slide show to tell the complete story of the section without loosing much details.

## Guidelines:
0. ! Use the language of the book for all your responses, e.g. if the book is in French, use French for all your responses.
1. Each card should represent ONE distinct, atomic idea from the text
2. Ensure cards collectively cover the COMPLETE content of the section
3. Use clear, precise language in the descriptions (< 2 sentences). Make use of bold HTML <b>tags</b> for emphasis.
4. Create simple, precise descriptions of PHOTOGRAPHIC illustration that gives understanding of the idea at first glance. The description should always be in English.
5. The illustration should be of a scene or a situation that is representative of the idea, there should be NO LABEL, NO DIAGRAM and NO TEXT
6. Extract 1 to 5 direct quotes that best exemplify each idea. Ensure quotes are full sentences that can be read as stand alone.
7. Include ideas that are not directly named in the text but are present, scattered or diffused accross the text

# Book section

{BOOK_SECTION}

"""

EXAMPLE_EXTRACTION_PROMPT = """
# Instruction
You are reading a long section of a book. Your role is to create {NB_CARD} (+/- 2 depending on the number of relevant examples) Zettelkasten cards using HTML formatting that highlight the key examples presented in this section. They sould be real-world applications, stories, case studies, metaphors the author uses to ground their arugments.

Every card has a title, a description, a type, an illustration and an ensemble of quotes that present or elaborate on the example.

Ensure the cards cover the most significant examples from this section. If I were to use these cards in a slide show to present the examples from the section to an audience, the cards would effectively showcase the practical applications and illustrations that the author uses to convey their points.

## Guidelines:
0. ! Use the language of the book for all your responses, e.g. if the book is in French, use French for all your responses.
1. Each card should represent ONE distinct example or case study from the text
2. Focus on concrete examples rather than abstract concepts
3. Use clear and concise descriptions (< 2 sentences). Make use of bold HTML <b>tags</b> for highlighting.
4. Create simple, precise descriptions of PHOTOGRAPHIC illustration that visually represents the example
5. The illustration should be of a scene or a situation that depicts the example
6. Extract 1 to 5 direct quotes that present or elaborate on the example. Ensure quotes are full sentences that can be read as stand alone.
7. Include real-world applications, stories, case studies, and instances that the author uses to support their arguments

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
