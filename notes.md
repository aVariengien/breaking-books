Those are my note of how the new architecture should likely be.


- Breaking Books - new architecture
	- On veut utilise claude code comme orchestrateur:
		- Agent - claude code sdk
			- Full book always in context
			- ReadFile
			- EditFile
			- QualityControl
			- This is in autonomous loop until it considers the work done. Can then be resumed with further instructions too
		- QualityControl - check cards.json is great
			- parse json and report errors
			- Sections equilibrées
			- Ask LLM
				- Est ce que tous les termes sont définis
				- Langue tjs la même et correcte
				- Style coherent?
				- Exhaustivité?
				- Intéressant? Well scoped?
				- Type adherence?
			- Check visual rendering
				- make the PDF then pngs
				- one vision LLM call per card, with png
				- is text cut ? Other visual issues?
				- Image bien formée?
			- Ouptputs a natural languague string of possible improvement, which the agent then incorportates (or not).
			- Each call to quality control saves a snapshot of the current deck + its report
			- QC is called only on the cards.json, and so will need to render tempates and generate images (call the functions to do it ofc)
		- Web interface
		- Schemas
			- definitions -> go in structured output
			- descriptions (when to use it) -> go in prompt
			- examples -> go in prompt
			- which templates match
		- Templates
			- for which schemas
			- jinja templaet
-
- src
	- schemas
		- concept.py
			-
			  ```py
			  class Schema(BaseModel):  # in lib/schema.py
			  	type: str
			      id: str
			      section: int
			      templates: ClassVar[list[str]]


			  class ConceptSchema(Schema):
			  	"""
			      Use concept cards to highlight...
			      For essays that introduce the reader to a new field, most cards will likely be concept cards.
			      """

			      type: Literal['concept']
			  	title: str
			      book_quotes: Anotated[list[str], Field(description="Verbatim quotes from the boot that buil this concept.")
			      image_description: str

			      templates = [
			      	'concept-image-left.jinja2',
			          'concept-image-right.jinja2',
			      ]

			  EXAMPLES = [
			  	ConceptSchema(...),
			  	ConceptSchema(...),
			  	ConceptSchema(...),
			  ]
			  ```
		- exercise.py
		- example.py
		- boat.py
		- ...
	- templates
		- concept-image-left.html.jinja2
		- concept-image-right.html.jinja2
		- big-quote.html.jinja2
		- ...
	- tools
		- extract-book-content
		- build-agent-prompt
		- quality-control
			- possibly as an agent that can be resumed
		- gather-external-sources (goodreads, wikipedia, deepresearch...)
		- generate-images
		- render-template-to-pdf (randomly select matching schema, jinja2, weasyprint)
		- pdf-to-pngs
		- merge-pdfs-to-print
	- lib (this doesn't feel very diferent from tools/, but the core difference is that tools is supposed to be closer to one step in the pipeline, but lib might be used multiple times in different places, or are about small technical details / code reuse)
		- models
			- Schema (id, section, tags?)
			- Card (union of all schemas)
		- gather templates/schemas
		- streamlit utils
		- logging
		- other utils?
	- agent.py
		- main claude code sdk agent definition
	- main.py
		- input, extract content, agent loop, output, assemble pdf/png zip
	- web.py -- streamlit UI
		- inputs, extract content, agent loop, output, presentation
		- followup, agent loop, new output (and repeat)
	- tests
		- we need to be able to test each part separately.
		- We want to be able to qualitatively asses quality too. so not just pytest, possibly some streamlit app
			- in the streamlit UI, one could select any stage of the pipeline, run it on sample data that we collected beforehand, and see the output to scan for errors / quality
            - when it makes sense, those should also be able to be ran from the command line so that AI agents can use them to iterate.
	- big_prompt.py
		- instructions for the steps to follow (decide on sections, write cards, do QC, repeat, card type manual, when to choose cards, which schemas of cards exist...)
		- with placeholders for examples, schemas, and the book.
	- And at the root, also dockerfile, things to deploy on fly.io, pre-commit...
- What and where is the data?
	- agent runs in an isolated folder TMP/
	- each step is a file in the folder. Things are passed around as filenames
	- but there's also a config
		- how many cards one wants
		- which size
		- user preference for some type of cards
		- language
		- max number of calls to quality control
	- comment la config est passée?
		- dans le prompt de l'agent, un build_prompt(book_path, config) (ou variation)
		- et en parametre de quality control soit avec partial(QC,  config=config) ou autre higher order function.
	- The whole state is
		- agent working directory
			- TMP/
				- cards.json
				- images/  # A cache mostly
					- {prompt1-hash}.png
					- {prompt2-hash}.png
				- renders/
					- card-001.pdf
					- card-001.png
					- card-002.pdf
					- ...
			- OUT/
				- cards-v001.json
				- qc-report-v001.md
				- cards-v002.json
				- qc-report-v002.md
		- output + snapshots + QC reports dir (outside agent working dir)
		- config
