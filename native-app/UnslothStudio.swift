// Unsloth Studio — minimal native macOS shell around the local studio web server.
// Ensures the LaunchAgent-hosted server (:8888) is up, then renders it in a WKWebView.
import AppKit
import WebKit

let base = URL(string: "http://127.0.0.1:8888")!

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    var window: NSWindow!
    let webView = WKWebView(frame: .zero)
    var attempts = 0
    var kicked = false
    var everLoaded = false

    func applicationDidFinishLaunching(_ note: Notification) {
        NSApp.setActivationPolicy(.regular)
        buildMenus()

        webView.navigationDelegate = self
        let rect = NSRect(x: 0, y: 0, width: 1320, height: 880)
        window = NSWindow(contentRect: rect,
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Unsloth Studio"
        window.minSize = NSSize(width: 900, height: 620)
        window.contentView = webView
        window.center()
        window.setFrameAutosaveName("UnslothStudioMain")
        window.makeKeyAndOrderFront(nil)

        checkAndLoad()
    }

    func buildMenus() {
        let main = NSMenu()
        // App menu with working Cmd+Q
        let appItem = NSMenuItem(); main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(NSMenuItem(title: "About Unsloth Studio",
                                   action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)),
                                   keyEquivalent: ""))
        appMenu.addItem(.separator())
        appMenu.addItem(NSMenuItem(title: "Hide Unsloth Studio",
                                   action: #selector(NSApplication.hide(_:)), keyEquivalent: "h"))
        appMenu.addItem(NSMenuItem(title: "Quit Unsloth Studio",
                                   action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        appItem.submenu = appMenu
        // Edit menu so text fields inside the webview support clipboard shortcuts
        let editItem = NSMenuItem(); main.addItem(editItem)
        let edit = NSMenu(title: "Edit"); editItem.submenu = edit
        edit.addItem(NSMenuItem(title: "Undo", action: Selector(("undo:")), keyEquivalent: "z"))
        edit.addItem(NSMenuItem(title: "Redo", action: Selector(("redo:")), keyEquivalent: "Z"))
        edit.addItem(.separator())
        edit.addItem(NSMenuItem(title: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x"))
        edit.addItem(NSMenuItem(title: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c"))
        edit.addItem(NSMenuItem(title: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v"))
        edit.addItem(NSMenuItem(title: "Select All",
                                action: #selector(NSText.selectAll(_:)), keyEquivalent: "a"))
        // View > Reload
        let viewItem = NSMenuItem(); main.addItem(viewItem)
        let view = NSMenu(title: "View"); viewItem.submenu = view
        view.addItem(NSMenuItem(title: "Reload",
                                action: #selector(reloadNow), keyEquivalent: "r"))
        NSApp.mainMenu = main
    }

    @objc func reloadNow() { loadBase() }

    func loadBase() {
        webView.load(URLRequest(url: base))
    }

    func checkAndLoad() {
        var req = URLRequest(url: URL(string: "http://127.0.0.1:8888/api/health")!)
        req.timeoutInterval = 2
        URLSession.shared.dataTask(with: req) { data, resp, _ in
            let ok = (resp as? HTTPURLResponse)?.statusCode == 200
            DispatchQueue.main.async {
                if ok {
                    self.loadBase()
                } else {
                    self.attempts += 1
                    // nudge the LaunchAgent exactly once after a short grace period
                    if self.attempts == 3 && !self.kicked {
                        self.kicked = true
                        let uid = getuid()
                        let p = Process()
                        p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
                        p.arguments = ["kickstart", "-k", "gui/\(uid)/com.user.unsloth.studio"]
                        try? p.run()
                    }
                    if self.attempts < 60 {
                        Timer.scheduledTimer(withTimeInterval: 2, repeats: false) { _ in
                            self.checkAndLoad()
                        }
                        self.webView.loadHTMLString(self.placeholder("Waiting for Unsloth Studio…"), baseURL: nil)
                    } else {
                        self.webView.loadHTMLString(
                            self.placeholder("Server did not come up.<br>Try: unsloth studio -p 8888"),
                            baseURL: nil)
                    }
                }
            }
        }.resume()
    }

    func placeholder(_ text: String) -> String {
        """
        <html><body style="font-family:-apple-system;display:flex;align-items:center;\
        justify-content:center;height:100vh;background:#101418;color:#9fb3c8;font-size:18px">\
        🦥 \(text)</body></html>
        """
    }

    func webView(_ wv: WKWebView, didFinish nav: WKNavigation!) {
        if wv.url?.host == base.host && !everLoaded { everLoaded = true }
    }

    // auto-retry while server cold-boots
    func webView(_ wv: WKWebView, didFail nav: WKNavigation!, withError error: Error) {
        guard !everLoaded else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self, !self.everLoaded else { return }
            self.loadBase()
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { window?.makeKeyAndOrderFront(nil) }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
