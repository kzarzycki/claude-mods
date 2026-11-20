# iOS simulator: simctl

On macOS with Xcode, `simctl` records a booted simulator's screen straight to H.264 MP4.

```sh
xcrun simctl status_bar booted override --time 9:41 --batteryState charged --batteryLevel 100
xcrun simctl io booted recordVideo --codec=h264 --force "$tmp/demo.mp4" &
rec=$!
# ... drive the app: an XCUITest, Maestro flow or other scripted run ...
kill -INT "$rec" && wait "$rec"
xcrun simctl status_bar booted clear
```

- Stop the recording with `SIGINT` and wait for it: that writes the file's index, and
  any other stop leaves a video that does not play.
- The status bar override keeps the clock and battery from distracting or dating the video.
