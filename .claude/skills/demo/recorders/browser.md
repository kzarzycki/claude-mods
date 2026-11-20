# Web page: Playwright video

Playwright records every page of a browser context to WebM when the context is created
with a video directory. The file is complete only after the context closes.

```ts
const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  recordVideo: { dir: tmp, size: { width: 1280, height: 720 } },
  storageState: "auth.json", // logged in before recording, so the video skips the login
});
const page = await context.newPage();
// ... the scenario ...
await context.close();
const webm = await page.video()!.path();
```

Python's equivalent is `browser.new_context(record_video_dir=tmp, record_video_size=...)`.
In Playwright Test, `use: { video: "on" }` records each test.

- Do setup (login, seed data) in a context without `recordVideo`, and save its
  `storageState` for the recorded one.
- Launch with `slowMo` (around 300 ms) so a viewer can follow clicks and typing.
- Pass the `.webm` to `scripts/demo.sh`, which converts it to H.264 MP4.
- A recording starts when the page is created, so a slow first load (a dev server compiling
  the page, a slow data request) puts a spinner at the head of the file, and waiting for the
  content does not remove it: the recorder is already running. Take it out of the file:
  1. Load the page once first in a context that does not record, which warms the dev server.
  2. In the recorded scenario, note `Date.now()` just before `context.newPage()`, wait for
     the content (`await expect(locator).toBeVisible()`), and note how long that took,
     `ready`.
  3. After `context.close()`, cut that much off the head with ffmpeg, and pass the `.mp4` to
     `scripts/demo.sh`: `ffmpeg -ss <ready + 0.1> -i in.webm -c:v libx264 -pix_fmt yuv420p
     -movflags +faststart out.mp4` (`-ss` before `-i` seeks exactly when it re-encodes).
  4. Check the cut: `ffmpeg -i out.mp4 -frames:v 1 first.png` must show the loaded content,
     not the spinner. A page with a 3 s data request gives a 6.8 s raw recording that starts
     blank and a 3 s cut whose first frame is the finished card.
- If nothing moves after the load, take a screenshot (`page.screenshot({ path })`) instead
  and pass the `.png` to `scripts/demo.sh`.
