from src.chunking import chunk_page, count_tokens, parse_html, parse_markdown

HTML = """<html><head><title>T</title></head><body><main>
<h1>Get a card</h1><p>Intro paragraph about the card.</p>
<h2>On this page</h2><ul><li><a href="#a">Who</a></li></ul>
<h2>Who can apply</h2><p>Residents of Ontario aged 16 or older.</p>
<ol><li><h3>Step 1</h3><p>Gather documents.</p></li>
<li><h3>Step 2</h3><p>Visit an office.</p></li></ol>
<script>var x = 1;</script>
</main></body></html>"""


def test_parse_html_splits_on_headings_and_descends_into_step_lists():
    page = parse_html(HTML)
    paths = [" > ".join(s.path) for s in page.sections]
    text = " ".join(s.text for s in page.sections)
    assert any("Who can apply" in p for p in paths)
    assert any("Step 2" in p for p in paths)  # headings inside <li> are kept
    assert "Visit an office." in text
    assert "var x" not in text and "On this page" not in " ".join(paths)


def test_chunk_windows_respect_size_and_overlap():
    md = "---\nid: x\nurl: u\ntitle: T\n---\n## Long\n" + " ".join(f"w{i}" for i in range(1200))
    _, page = parse_markdown(md)
    chunks = chunk_page(page, size=300, overlap=80)
    assert len(chunks) > 1
    assert all(c.n_tokens <= 300 for c in chunks)
    first, second = chunks[0].body.split(), chunks[1].body.split()
    assert first[-1] in second  # consecutive windows overlap


def test_count_tokens_counts_words_and_punctuation():
    assert count_tokens("Hello, world.") == 4
