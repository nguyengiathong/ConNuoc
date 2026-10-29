package io.github.nguyengiathong.connuoc;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.ViewGroup;
import android.view.Window;
import android.webkit.JavascriptInterface;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import androidx.core.graphics.ColorUtils;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import androidx.webkit.WebViewAssetLoader;

/** Hosts the Con Nước page (bundled under assets/www) in a full-screen WebView. */
public class MainActivity extends Activity {

    // Served from an https origin so fetch(), localStorage and the clipboard work as on the web.
    private static final String START_URL =
            "https://" + WebViewAssetLoader.DEFAULT_DOMAIN + "/assets/www/index.html";
    // After this long in the background the page is reloaded so "now" and today's date are current.
    private static final long STALE_AFTER_MS = 30 * 60 * 1000;

    private FrameLayout root;
    private WebView web;
    private long pausedAt;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window window = getWindow();
        WindowCompat.setDecorFitsSystemWindows(window, false);
        window.setStatusBarColor(Color.TRANSPARENT);
        window.setNavigationBarColor(Color.TRANSPARENT);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) window.setNavigationBarContrastEnforced(false);

        WebView.setWebContentsDebuggingEnabled((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0);
        root = new FrameLayout(this);
        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

        // Draw edge to edge, keeping the page clear of the system bars, cutouts and keyboard.
        ViewCompat.setOnApplyWindowInsetsListener(root, (v, insets) -> {
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            Insets ime = insets.getInsets(WindowInsetsCompat.Type.ime());
            v.setPadding(bars.left, bars.top, bars.right, Math.max(bars.bottom, ime.bottom));
            return WindowInsetsCompat.CONSUMED;
        });
        applyBackground(getColor(R.color.page_background));

        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        web.setBackgroundColor(Color.TRANSPARENT);
        web.addJavascriptInterface(new Bridge(), "ConNuocAndroid");

        WebViewAssetLoader assets = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return assets.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (WebViewAssetLoader.DEFAULT_DOMAIN.equals(uri.getHost())) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (ActivityNotFoundException ignored) {
                    // nothing can open the link
                }
                return true;
            }

            @Override
            public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
                // The renderer was killed (usually for memory): start over instead of crashing.
                root.removeView(view);
                view.destroy();
                web = null;
                recreate();
                return true;
            }
        });

        if (savedInstanceState == null || web.restoreState(savedInstanceState) == null) {
            web.loadUrl(START_URL);
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (web != null) web.saveState(outState);
    }

    @Override
    protected void onPause() {
        super.onPause();
        pausedAt = SystemClock.elapsedRealtime();
        if (web != null) web.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web == null) return;
        web.onResume();
        if (pausedAt != 0 && SystemClock.elapsedRealtime() - pausedAt > STALE_AFTER_MS) web.reload();
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            root.removeView(web);
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }

    /** Paints the area behind the system bars like the page and picks readable bar icons. */
    private void applyBackground(int color) {
        root.setBackgroundColor(color);
        getWindow().getDecorView().setBackgroundColor(color);
        boolean light = ColorUtils.calculateLuminance(color) > 0.5;
        WindowInsetsControllerCompat bars = WindowCompat.getInsetsController(getWindow(), root);
        bars.setAppearanceLightStatusBars(light);
        bars.setAppearanceLightNavigationBars(light);
    }

    /** Exposed to the page as window.ConNuocAndroid (see assets/www/android.js). */
    public final class Bridge {
        @JavascriptInterface
        public void copyText(String text) {
            runOnUiThread(() -> {
                ClipboardManager clipboard = getSystemService(ClipboardManager.class);
                clipboard.setPrimaryClip(ClipData.newPlainText(getString(R.string.app_name), text));
            });
        }

        @JavascriptInterface
        public void setBackground(String hex) {
            int color;
            try {
                color = Color.parseColor(hex);
            } catch (IllegalArgumentException e) {
                return;
            }
            runOnUiThread(() -> applyBackground(color));
        }
    }
}
