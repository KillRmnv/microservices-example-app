package com.microservices_example_app.gateway;

import io.github.bonigarcia.wdm.WebDriverManager;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.By;
import org.openqa.selenium.WebElement;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import com.sun.net.httpserver.HttpServer;

import static org.assertj.core.api.Assertions.assertThat;

class SeleniumTestBase {

    protected static WebDriver driver;
    protected static HttpServer server;
    protected static int port;
    private static final Path STATIC_DIR = Path.of("src/main/resources/static");

    @BeforeAll
    static void startBrowser() {
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

    @BeforeAll
    static void startServer() throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        port = server.getAddress().getPort();

        server.createContext("/", exchange -> {
            String path = exchange.getRequestURI().getPath();
            if (path.equals("/")) path = "/index.html";

            Path file = STATIC_DIR.resolve(path.substring(1));
            if (Files.exists(file) && !Files.isDirectory(file)) {
                byte[] bytes = Files.readAllBytes(file);
                String contentType = guessContentType(path);
                exchange.getResponseHeaders().set("Content-Type", contentType + "; charset=UTF-8");
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

    @AfterAll
    static void stopAll() {
        if (driver != null) driver.quit();
        if (server != null) server.stop(0);
    }

    @BeforeEach
    void setUp() {
        driver.get("http://localhost:" + port + "/");
        waitForJs();
    }

    protected void waitForJs() {
        try { Thread.sleep(500); } catch (InterruptedException ignored) {}
    }

    protected void navigateTo(String hash) {
        ((JavascriptExecutor) driver).executeScript("window.location.hash = '" + hash + "'");
        waitForJs();
    }

    protected Object js(String script) {
        return ((JavascriptExecutor) driver).executeScript(script);
    }

    protected String jsString(String script) {
        Object result = js(script);
        return result != null ? result.toString() : null;
    }

    protected WebElement find(String cssSelector) {
        return driver.findElement(By.cssSelector(cssSelector));
    }

    protected List<WebElement> findAll(String cssSelector) {
        return driver.findElements(By.cssSelector(cssSelector));
    }

    private static String guessContentType(String path) {
        if (path.endsWith(".html")) return "text/html";
        if (path.endsWith(".js")) return "application/javascript";
        if (path.endsWith(".css")) return "text/css";
        if (path.endsWith(".json")) return "application/json";
        if (path.endsWith(".png")) return "image/png";
        if (path.endsWith(".jpg")) return "image/jpeg";
        if (path.endsWith(".svg")) return "image/svg+xml";
        return "application/octet-stream";
    }
}
