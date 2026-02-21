-- remove_footnotes.lua
function Note (note_element)
  -- This function is called for every footnote element.
  -- Returning an empty list of Inlines effectively removes the footnote.
  return {}
end

function Cite (cite_element)
  -- This function is called for every citation element.
  -- Returning an empty list of Inlines effectively removes the citation.
  return {}
end

function Link (link_element)
  -- If this is a footnote reference (indicated by ^), remove it
  if link_element.target:match("^#fn") then
    return {}
  end
  -- Otherwise keep the link unchanged
  return link_element
end
