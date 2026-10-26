"""Drive the running app like a user and save the shots for the demo video.

    python demo/record.py            (the app must be running on http://localhost:8010)

Writes demo/build/shots/*.png and demo/build/storyboard.json, which demo/render.py turns
into the video. Each segment says which screenshot to show, how long, where the camera
should zoom, where the cursor goes, and which caption is on screen.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://localhost:8010"
OUT = Path(__file__).parent / "build"
SHOTS = OUT / "shots"
VIEW_W, VIEW_H, SCALE = 1600, 900, 1.2  # screenshots come out at 1920x1080

CAPTIONS = {
    "overview": ("OVERVIEW", "Ask your contracts. Get clear answers.",
                 "An AI assistant for procurement teams. Every answer points to the exact clause it came from."),
    "measured": ("MEASURED", "Tested on real contracts",
                 "Retrieval is tested on 675 questions over lawyer-labeled contracts from the CUAD dataset."),
    "start": ("GET STARTED", "Into the app", "Three pages: Chat, Contracts and Evaluation."),
    "chat": ("CHAT", "Ask in English or Arabic",
             "Questions about contract terms and purchase-order data, all in one chat."),
    "grounded": ("GROUNDED ANSWERS", "Every answer cites its source",
                 "The cited clause appears beside the answer, with a confidence level."),
    "verify": ("VERIFY", "See it in the full contract",
               "One click opens the whole contract, scrolled to the highlighted clause."),
    "crossling": ("CROSS-LINGUAL", "Arabic question, English contract",
                  "Multilingual embeddings match meaning across languages. The answer comes back in Arabic."),
    "sql": ("TEXT-TO-SQL", "Numbers come from the database",
            "Data questions become a read-only SQL query, shown in full so it can be checked."),
    "nogues": ("NO GUESSING", "If the contract doesn't say, it says so",
               "Answers use only the retrieved clauses. Missing information is reported, never invented."),
    "contracts": ("CONTRACTS", "Track renewals at a glance",
                  "104 contracts with status and dates, and an alert for those expiring within 60 days."),
    "search": ("SEARCH", "Find any supplier, in either language",
               "Search by supplier name in English or Arabic, then open the contract in the chat."),
    "eval": ("EVALUATION", "91.7% retrieval accuracy",
             "Recall@5 on lawyer-labeled clauses, plus LLM-judged faithfulness of the answers."),
    "tradeoff": ("TRADE-OFFS", "Every step is measured",
                 "Four versions side by side: the current one is the most accurate, at about half a second per question."),
}


class Recorder:
    def __init__(self, page: Page):
        self.page = page
        self.segments: list[dict] = []
        self.n = 0

    def shot(self) -> str:
        self.n += 1
        path = SHOTS / f"{self.n:03d}.png"
        self.page.screenshot(path=str(path))
        return path.name

    def box(self, selector: str, nth: int = 0, pad: int = 0) -> list[float] | None:
        """Bounding box of an element in screenshot pixels."""
        loc = self.page.locator(selector).nth(nth)
        b = loc.bounding_box()
        if not b:
            return None
        return [(b["x"] - pad) * SCALE, (b["y"] - pad) * SCALE, (b["width"] + 2 * pad) * SCALE,
                (b["height"] + 2 * pad) * SCALE]

    def center(self, selector: str, nth: int = 0) -> list[float] | None:
        b = self.box(selector, nth)
        return [b[0] + b[2] / 2, b[1] + b[3] / 2] if b else None

    def add(self, img: str, dur: float, *, zoom=None, cursor=None, click=False, caption=None,
            transition="cut", sfx=(), caption_top=False):
        self.segments.append({"img": img, "dur": dur, "zoom": zoom, "cursor": cursor, "click": click,
                              "caption": CAPTIONS[caption] if caption else None,
                              "transition": transition, "sfx": list(sfx), "caption_top": caption_top})

    def type_question(self, text: str, caption: str):
        box = self.page.locator('input[placeholder="Ask about the contracts…"]')
        input_zoom = self.box('form', 0, pad=40)
        self.add(self.shot(), 0.8, zoom=input_zoom, cursor=self.center('form input'), click=True, caption=caption,
                 transition="fade")
        step = max(1, len(text) // 14)
        for k in range(step, len(text) + step, step):
            box.fill(text[:k])
            self.add(self.shot(), 0.11, zoom=input_zoom, sfx=["type"])
        self.add(self.shot(), 0.5, zoom=input_zoom, cursor=self.center('button[aria-label="Send"]'), click=True)
        box.press("Enter")
        self.page.wait_for_timeout(700)
        self.add(self.shot(), 1.2, zoom=None, caption=caption)
        self.page.wait_for_function(
            "() => !document.body.innerText.includes('Searching the contracts')", timeout=300_000)
        self.page.wait_for_timeout(1200)

    def answer_bubble(self) -> list[float] | None:
        count = self.page.locator("main section .bg-ink-850.rounded-xl").count()
        return self.box("main section .bg-ink-850.rounded-xl", count - 1, pad=60) if count else None


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    for old in SHOTS.glob("*.png"):
        old.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": VIEW_W, "height": VIEW_H}, device_scale_factor=SCALE)
        r = Recorder(page)

        # Landing page
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        # The camera only zooms in on what is being clicked or typed into; everything else is
        # shown full-frame.
        hero = r.shot()
        r.add(hero, 5.0, caption="overview", transition="fade")

        page.locator("h2", has_text="Measured results").scroll_into_view_if_needed()
        page.evaluate("window.scrollBy(0, 160)")
        page.wait_for_timeout(600)
        r.add(r.shot(), 4.6, caption="measured", transition="fade")

        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(400)
        r.add(r.shot(), 1.6, caption="start", transition="fade",
              cursor=r.center("a.bg-accent"), click=True, zoom=r.box("a.bg-accent", pad=140))
        page.locator("a.bg-accent").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Chat: grounded answer and the clause
        r.add(r.shot(), 2.6, caption="chat", transition="fade")
        r.type_question("What is the late delivery penalty for Al-Sharq Pharma?", "chat")
        r.add(r.shot(), 5.5, caption="grounded", transition="fade",
              cursor=r.center('button[aria-label^="Show source"]'))

        full_button = "button:has-text('Show in full contract')"
        r.add(r.shot(), 1.4, caption="verify", zoom=r.box(full_button, pad=120),
              cursor=r.center(full_button), click=True)
        page.locator(full_button).click()
        page.wait_for_timeout(900)
        r.add(r.shot(), 3.8, transition="fade")

        # Cross-lingual
        r.type_question("ما غرامة التأخير في عقد نجد للتوزيع؟", "crossling")
        r.add(r.shot(), 5.5, transition="fade")

        # Text-to-SQL
        r.type_question("Which supplier has the most late deliveries?", "sql")
        r.add(r.shot(), 5.5, transition="fade")

        # No guessing
        r.type_question("What is the Al-Sharq Pharma CEO's name?", "nogues")
        r.add(r.shot(), 5.0, transition="fade")

        # Contracts
        page.get_by_role("link", name="Contracts").click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        r.add(r.shot(), 5.0, caption="contracts", transition="fade",
              cursor=r.center("button:has-text('expire in the next')"))

        search = page.locator('input[aria-label="Search contracts"]')
        search_zoom = r.box("section.card", pad=0)
        r.add(r.shot(), 0.9, caption="search", transition="fade", zoom=search_zoom,
              cursor=r.center('input[aria-label="Search contracts"]'), click=True)
        word = "الرياض"
        for k in range(1, len(word) + 1):
            search.fill(word[:k])
            r.add(r.shot(), 0.14, zoom=search_zoom, sfx=["type"])
        page.wait_for_timeout(300)
        found = r.shot()
        r.add(found, 2.2, cursor=r.center("tbody a"))
        r.add(found, 0.9, zoom=r.box("tbody tr", pad=80), cursor=r.center("tbody a"), click=True)
        page.locator("tbody a").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(900)
        r.add(r.shot(), 2.6, transition="fade", cursor=r.center("main select"))

        # Evaluation
        page.get_by_role("link", name="Evaluation").click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)
        r.add(r.shot(), 5.0, caption="eval", transition="fade")

        page.locator("h2", has_text="Accuracy vs. speed").scroll_into_view_if_needed()
        page.evaluate("window.scrollBy(0, -40)")
        page.wait_for_timeout(500)
        r.add(r.shot(), 5.0, caption="tradeoff", transition="fade", caption_top=True)  # the chart is at the bottom

        browser.close()

    (OUT / "storyboard.json").write_text(json.dumps(
        {"width": int(VIEW_W * SCALE), "height": int(VIEW_H * SCALE), "segments": r.segments}, indent=1),
        encoding="utf-8")
    print(f"{len(r.segments)} segments, {r.n} screenshots, "
          f"{sum(s['dur'] for s in r.segments):.0f}s of footage -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
