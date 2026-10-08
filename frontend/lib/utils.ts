import { createCn } from "cn/config"

// Our type scale (text-meta … text-hero) must be known as font sizes; otherwise
// the merge treats it as a colour and drops it next to text-impact-high etc.
export const cn = createCn({
  extend: { classGroups: { "font-size": [{ text: ["meta", "dense", "body", "section", "title", "hero"] }] } },
})
