package com.microservices_example_app.gateway;

import io.github.bonigarcia.wdm.WebDriverManager;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;

import com.sun.net.httpserver.HttpServer;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Base for Selenium view tests against the new Next.js frontend.
 *
 * <p>By default the prebuilt static export is served locally from
 * {@code FRONTEND_DIR} (default {@code ../frontend/out}, build it with
 * {@code cd frontend && pnpm build}). Set {@code FRONTEND_URL} to drive an
 * already running frontend instead (e.g. {@code http://localhost:3000} from
 * {@code docker compose up frontend}) — the embedded server is skipped then.
 *
 * <p>No backend is required: tests assert static chrome (masthead, nav,
 * forms) and the offline/error states the pages render when the API is
 * unreachable.
 */
class SeleniumTestBase {

    protected static WebDriver driver;
    protected static HttpServer server;
    protected static String frontendUrl;

    private static final Duration TIMEOUT = Duration.ofSeconds(10);

    @BeforeAll
    static void startAll() throws IOException {
        String explicit = System.getenv("FRONTEND_URL");
        if (explicit != null && !explicit.isBlank()) {
            frontendUrl = explicit;
        } else {
            Path dir = Path.of(envOrDefault("FRONTEND_DIR", "../frontend/out"));
            if (!Files.isDirectory(dir)) {
                throw new IllegalStateException(
                        "Frontend export not found at " + dir.toAbsolutePath()
                                + ". Build it first: cd frontend && pnpm install && pnpm build");
            }
            startStaticServer(dir);
            frontendUrl = "http://localhost:" + server.getAddress().getPort();
        }
        startBrowser();
    }

    @AfterAll
    static void stopAll() {
        if (driver != null) driver.quit();
        if (server != null) server.stop(0);
    }

    @BeforeEach
    void resetBrowserState() {
        driver.get(frontendUrl + "/");
        waitForPageLoad();
        driver.manage().deleteAllCookies();
        js("try { localStorage.clear(); sessionStorage.clear(); } catch (e) {}");
    }

    protected void navigateTo(String path) {
        driver.get(frontendUrl + path);
        waitForPageLoad();
    }

    protected void waitForPageLoad() {
        new WebDriverWait(driver, TIMEOUT).until(
                d -> "complete".equals(jsString("return document.readyState")));
    }

    protected void waitForUrlContains(String part) {
        new WebDriverWait(driver, TIMEOUT).until(d -> d.getCurrentUrl().contains(part));
    }

    protected WebElement waitFor(By locator) {
        return new WebDriverWait(driver, TIMEOUT)
                .until(d -> d.findElement(locator));
    }

    protected WebElement findByTestId(String testId) {
        return waitFor(By.cssSelector("[data-testid='" + testId + "']"));
    }

    protected List<WebElement> findAllByTestId(String testId) {
        waitForPageLoad();
        return driver.findElements(By.cssSelector("[data-testid='" + testId + "']"));
    }

    protected WebElement find(String cssSelector) {
        return waitFor(By.cssSelector(cssSelector));
    }

    protected List<WebElement> findAll(String cssSelector) {
        waitForPageLoad();
        return driver.findElements(By.cssSelector(cssSelector));
    }

    protected Object js(String script) {
        return ((JavascriptExecutor) driver).executeScript(script);
    }

    protected String jsString(String script) {
        Object result = js(script);
        return result != null ? result.toString() : null;
    }

    private static String envOrDefault(String key, String def) {
        String value = System.getenv(key);
        return value != null && !value.isBlank() ? value : def;
    }

    private static void startBrowser() {
        WebDriverManager.chromedriver().setup();
        ChromeOptions options = new ChromeOptions();
        options.addArguments("--headless=new");
        options.addArguments("--no-sandbox");
        options.addArguments("--disable-dev-shm-usage");
        options.addArguments("--disable-gpu");
        options.addArguments("--window-size=1920,1080");
        options.addArguments("--lang=ru-RU");
        driver = new ChromeDriver(options);
    }

    private static void startStaticServer(Path exportDir) throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/", exchange -> {
            String rawPath = exchange.getRequestURI().getPath();
            Path file = resolveExportFile(exportDir, rawPath);
            if (file != null) {
                byte[] bytes = Files.readAllBytes(file);
                exchange.getResponseHeaders().set(
                        "Content-Type", guessContentType(file.getFileName().toString()) + "; charset=UTF-8");
                exchange.sendResponseHeaders(200, bytes.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(bytes);
                }
            } else {
                byte[] notFound = "Not Found".getBytes();
                exchange.sendResponseHeaders(404, notFound.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(notFound);
                }
            }
        });
        server.start();
    }

    /** Next.js static export: {@code /login} lives at {@code login.html} or {@code login/index.html}. */
    private static Path resolveExportFile(Path exportDir, String rawPath) {
        if (rawPath.endsWith("/")) rawPath += "index.html";
        String relative = rawPath.startsWith("/") ? rawPath.substring(1) : rawPath;
        if (relative.isEmpty()) relative = "index.html";
        // Strip query leftovers defensively (getPath already excludes them, but be safe).
        int query = relative.indexOf('?');
        if (query >= 0) relative = relative.substring(0, query);

        Path direct = exportDir.resolve(relative).normalize();
        if (!direct.startsWith(exportDir)) return null;
        if (Files.isRegularFile(direct)) return direct;
        if (Files.isDirectory(direct)) {
            Path index = direct.resolve("index.html");
            if (Files.isRegularFile(index)) return index;
        }
        if (!relative.contains(".")) {
            Path html = exportDir.resolve(relative + ".html").normalize();
            if (html.startsWith(exportDir) && Files.isRegularFile(html)) return html;
            Path nested = exportDir.resolve(relative + "/index.html").normalize();
            if (nested.startsWith(exportDir) && Files.isRegularFile(nested)) return nested;
        }
        return null;
    }

    private static String guessContentType(String fileName) {
        if (fileName.endsWith(".html")) return "text/html";
        if (fileName.endsWith(".js")) return "application/javascript";
        if (fileName.endsWith(".css")) return "text/css";
        if (fileName.endsWith(".json")) return "application/json";
        if (fileName.endsWith(".png")) return "image/png";
        if (fileName.endsWith(".jpg") || fileName.endsWith(".jpeg")) return "image/jpeg";
        if (fileName.endsWith(".webp")) return "image/webp";
        if (fileName.endsWith(".svg")) return "image/svg+xml";
        if (fileName.endsWith(".ico")) return "image/x-icon";
        if (fileName.endsWith(".woff2")) return "font/woff2";
        if (fileName.endsWith(".woff")) return "font/woff";
        if (fileName.endsWith(".ttf")) return "font/ttf";
        if (fileName.endsWith(".map")) return "application/json";
        if (fileName.endsWith(".txt") || fileName.endsWith(".xml")) return "text/plain";
        return "application/octet-stream";
    }

    protected void assertMastheadPresent() {
        assertThat(find(".brand h1 a").getText()).isEqualTo("ДОСУГ");
        assertThat(findByTestId("newspaper-nav")).isNotNull();
    }
}
