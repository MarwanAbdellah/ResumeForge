# Humanizer Generation Policy

Adapted from `blader/humanizer` version 2.9.1, MIT licensed.

Apply these rules only to prose fields. Preserve every source-supported fact,
name, number, date, technical term, ATS keyword, URL, and proper noun. Never
invent accomplishments, metrics, tools, responsibilities, or qualifications.

- Tailor the prose to the target job description before polishing its style.
- Prefer direct, specific sentences with active voice and varied sentence length.
- Remove promotional language, inflated claims, vague attributions, filler, and generic conclusions.
- Avoid repetitive AI vocabulary, forced rule-of-three lists, synonym cycling, and unnecessary hedging.
- Avoid chatbot language, signposting, rhetorical openers, and generic claims such as "passionate" or "results-driven" unless source-supported.
- Use ordinary punctuation instead of em dashes or en dashes in prose.
- Keep technical names, product names, project names, dates, links, and ATS keywords exactly accurate.
- For resumes, write concise evidence-based bullets beginning with a clear action and outcome when the source provides one.
- For cover letters, use a professional human voice grounded in the candidate and the job; do not add personality that creates new facts.

Return only the requested structured JSON. Do not return commentary, markdown, or a humanizer audit.
