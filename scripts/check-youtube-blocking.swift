import Cocoa
import WebKit

final class Harness: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
    let app: NSApplication
    var webView: WKWebView!
    let blocker: String
    let blockerEnabled: Bool
    let unrelatedHost: Bool
    let expectAds: Bool
    var finished = false

    init(app: NSApplication) throws {
        self.app = app
        let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        blocker = try String(contentsOf: root.appendingPathComponent("firefox-ios/Client/Assets/YouTubeAdBlocking.js"), encoding: .utf8)
        blockerEnabled = !CommandLine.arguments.contains("--disabled")
        unrelatedHost = CommandLine.arguments.contains("--unrelated")
        expectAds = unrelatedHost || !blockerEnabled
        super.init()
        let configuration = WKWebViewConfiguration()
        let controller = WKUserContentController()
        controller.add(self, name: "harness")
        controller.addUserScript(WKUserScript(source: """
        (() => {
          const originalWarn = console.warn;
          console.warn = (...args) => { window.webkit.messageHandlers.harness.postMessage('WARN:' + args.join(' ')); originalWarn(...args); };
          const realResponse = {adPlacements:[1], playerAds:[2], adSlots:[3], streamingData:{formats:[1]}, videoDetails:{title:'fixture'}};
          window.fetch = async (input, init) => {
            return new Response(JSON.stringify(realResponse), {headers:{'Content-Type':'application/json'}});
          };
        })();
        """, injectionTime: .atDocumentStart, forMainFrameOnly: false, in: .page))
        if blockerEnabled {
            controller.addUserScript(WKUserScript(source: blocker, injectionTime: .atDocumentStart,
                                                   forMainFrameOnly: false, in: .page))
        }
        configuration.userContentController = controller
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
    }

    func run() {
        let html = """
        <!doctype html><script>
        window.ytInitialPlayerResponse = {adPlacements:[1],playerAds:[2],adSlots:[3],streamingData:{formats:[1]},videoDetails:{title:'fixture'}};
        window.addEventListener('load', async () => {
          const player = await fetch('/youtubei/v1/player?key=fixture').then(r => r.json());
          const untouched = await fetch('/youtubei/v1/other').then(r => r.json());
          const expectedAds = \(expectAds ? "true" : "false");
          const adFields = ['adPlacements', 'playerAds', 'adSlots'];
          const hasAds = value => adFields.every((key, index) => JSON.stringify(value[key]) === '[' + (index + 1) + ']');
          const noAds = value => adFields.every(key => value[key] === undefined);
          const preservesVideo = value => JSON.stringify(value.streamingData) === '{"formats":[1]}' &&
            JSON.stringify(value.videoDetails) === '{"title":"fixture"}';
          const matches = value => (expectedAds ? hasAds(value) : noAds(value)) && preservesVideo(value);
          window.__harnessResult = {
            globals: matches(ytInitialPlayerResponse),
            fetch: matches(player),
            other: hasAds(untouched) && preservesVideo(untouched),
          };
          window.webkit.messageHandlers.harness.postMessage(JSON.stringify(window.__harnessResult));
        });
        </script>
        """
        let baseURL = unrelatedHost ? URL(string: "https://example.org/page")! : URL(string: "https://www.youtube.com/watch?v=fixture")!
        webView.loadHTMLString(html, baseURL: baseURL)
        DispatchQueue.main.asyncAfter(deadline: .now() + 10) { [weak self] in
            guard let self, !finished else { return }
            fputs("timeout\n", stderr)
            exit(1)
        }
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "harness" else { return }
        let json = String(describing: message.body)
        if json.hasPrefix("WARN:") {
            fputs("YouTube blocking smoke warning: " + json + "\n", stderr)
            exit(1)
        }
        finished = true
        let results = (try? JSONSerialization.jsonObject(with: Data(json.utf8))) as? [String: Bool]
        if ["globals", "fetch", "other"].allSatisfy({ results?[$0] == true }) {
            print("YouTube blocking smoke: PASS")
            app.terminate(nil)
            return
        }
        fputs("YouTube blocking smoke: FAIL " + json + "\n", stderr)
        exit(1)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        fputs("navigation failed: \(error)\n", stderr)
        exit(1)
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
do {
    let harness = try Harness(app: app)
    harness.run()
    app.run()
} catch {
    fputs("harness setup failed: \(error)\n", stderr)
    exit(1)
}
