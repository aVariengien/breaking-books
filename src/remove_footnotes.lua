-- remove_footnotes.lua
function Note (note_element)
  -- This function is called for every footnote element.
  -- Returning an empty list of Inlines effectively removes the footnote.
  return {}
end
