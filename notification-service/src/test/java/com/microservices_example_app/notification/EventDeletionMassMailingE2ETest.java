package com.microservices_example_app.notification;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.bonigarcia.wdm.WebDriverManager;
import jakarta.mail.*;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;
import jakarta.mail.internet.MimeMultipart;
import org.junit.jupiter.api.*;
import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Properties;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("e2e")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class EventDeletionMassMailingE2ETest {

    private static WebDriver driver;
    private static HttpClient httpClient;
    private static final ObjectMapper objectMapper = new ObjectMapper();

    private static final String GATEWAY_URL = "http://localhost:8080";
    private static final String GMAIL_HOST = "imap.gmail.com";
    private static final int GMAIL_PORT = 993;
    private static final int EMAIL_WAIT_SECONDS = 180;
    private static final String EVENT_TITLE = "UFC Public Screening";

    private static String gmailBase;
    private static String gmailPassword;

    private static String managerJwt;
    private static String managerEmail;
    private static final String MANAGER_PASSWORD = "TestPass123!";
    private static String managerUsername;

    private static String customer1Jwt;
    private static String customer1Email;
    private static final String CUSTOMER_PASSWORD = "TestPass123!";
    private static String customer1Username;

    private static String customer2Jwt;
    private static String customer2Email;
    private static String customer2Username;

    private static Integer eventId;

    private record EmailData(String subject, String from, String body) {}

    @BeforeAll
    static void setup() throws Exception {
        String gmailUser = System.getenv("GMAIL_USERNAME");
        gmailPassword = System.getenv("GMAIL_PASSWORD");

        if (gmailUser == null || gmailUser.isBlank() || gmailPassword == null || gmailPassword.isBlank()) {
            throw new IllegalStateException(
                    "GMAIL_USERNAME and GMAIL_PASSWORD env vars must be set (use Gmail app password)");
        }

        gmailBase = gmailUser.contains("@") ? gmailUser.substring(0, gmailUser.indexOf('@')) : gmailUser;

        long ts = System.currentTimeMillis();
        managerEmail = gmailBase + "+manager" + ts + "@gmail.com";
        managerUsername = "e2e_manager_" + ts;

        customer1Email = gmailBase + "+cust1_" + ts + "@gmail.com";
        customer1Username = "e2e_cust1_" + ts;

        customer2Email = gmailBase + "+cust2_" + ts + "@gmail.com";
        customer2Username = "e2e_cust2_" + ts;

        httpClient = HttpClient.newHttpClient();

        startDockerCompose();
        waitForServicesHealthy();
        startBrowser();
    }

    @AfterAll
    static void teardown() {
        if (driver != null) {
            try { driver.quit(); } catch (Exception ignored) {}
        }
        stopDockerCompose();
    }

    @Test
    @Order(1)
    @DisplayName("Register EVENT_MANAGER and 2 CUSTOMERs via API")
    void testRegisterUsers() throws Exception {
        managerJwt = registerAndLogin("EVENT_MANAGER", managerUsername, managerEmail, MANAGER_PASSWORD);
        customer1Jwt = registerAndLogin("CUSTOMER", customer1Username, customer1Email, CUSTOMER_PASSWORD);
        customer2Jwt = registerAndLogin("CUSTOMER", customer2Username, customer2Email, CUSTOMER_PASSWORD);
    }

    @Test
    @Order(2)
    @DisplayName("Find seeded event and buy tickets for 2 customers")
    void testBuyTickets() throws Exception {
        String encodedTitle = URLEncoder.encode(EVENT_TITLE, StandardCharsets.UTF_8);
        String searchPath = "/booking/events/search?title=" + encodedTitle + "&page=1&size=10";

        HttpResponse<String> searchResp = sendGet(searchPath, customer1Jwt);
        assertThat(searchResp.statusCode()).as("Event search should return 200").isEqualTo(200);

        JsonNode events = objectMapper.readTree(searchResp.body());
        assertThat(events.size()).as("Should find at least one event").isGreaterThanOrEqualTo(1);

        for (JsonNode event : events) {
            if (EVENT_TITLE.equals(event.get("title").asText())) {
                eventId = event.get("id").asInt();
                break;
            }
        }
        assertThat(eventId).as("Event '" + EVENT_TITLE + "' should exist").isNotNull();

        buyTicket(customer1Jwt, eventId);
        buyTicket(customer2Jwt, eventId);
    }

    @Test
    @Order(3)
    @DisplayName("Verify event visible in UI via Selenium")
    void testEventVisibleInUI() throws Exception {
        injectJwtAndNavigate(customer1Jwt);

        WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(20));
        wait.until(d -> !d.findElements(By.cssSelector("#events-grid .event-card")).isEmpty());

        List<WebElement> cards = driver.findElements(By.cssSelector("#events-grid .event-card"));
        boolean found = cards.stream().anyMatch(card -> {
            try {
                return card.findElement(By.tagName("h3")).getText().contains(EVENT_TITLE);
            } catch (Exception e) {
                return false;
            }
        });
        assertThat(found).as("Event should be visible in UI before deletion").isTrue();
    }

    @Test
    @Order(4)
    @DisplayName("Delete event as EVENT_MANAGER")
    void testDeleteEvent() throws Exception {
        HttpResponse<String> resp = sendDelete("/booking/events/" + eventId, managerJwt);
        assertThat(resp.statusCode()).as("Delete should return 200").isEqualTo(200);
    }

    @Test
    @Order(5)
    @DisplayName("Verify event deleted via API (404)")
    void testVerifyEventDeletedViaApi() throws Exception {
        HttpResponse<String> resp = sendGet("/booking/events/" + eventId, managerJwt);
        assertThat(resp.statusCode()).as("Deleted event should return 404").isEqualTo(404);
    }

    @Test
    @Order(6)
    @DisplayName("Verify event gone from UI via Selenium")
    void testVerifyEventGoneFromUI() throws Exception {
        injectJwtAndNavigate(customer1Jwt);

        WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(20));
        wait.until(d -> d.findElements(By.cssSelector("#events-grid .event-card")).size() > 0
                || d.findElements(By.cssSelector("#events-grid p")).size() > 0
                || d.findElements(By.cssSelector("#events-grid .alert")).size() > 0);

        List<WebElement> cards = driver.findElements(By.cssSelector("#events-grid .event-card"));
        boolean found = cards.stream().anyMatch(card -> {
            try {
                return card.findElement(By.tagName("h3")).getText().contains(EVENT_TITLE);
            } catch (Exception e) {
                return false;
            }
        });
        assertThat(found).as("Deleted event should NOT be visible in UI").isFalse();
    }

    @Test
    @Order(7)
    @DisplayName("Verify mass mailing emails received via IMAP")
    void testVerifyMassMailingEmails() throws Exception {
        String imapUser = gmailBase + "@gmail.com";
        List<EmailData> emails = waitForEmails(
                imapUser, gmailPassword,
                "Event cancellation notice",
                2, EMAIL_WAIT_SECONDS);

        assertThat(emails.size())
                .as("Should receive at least 2 cancellation emails")
                .isGreaterThanOrEqualTo(2);

        boolean cust1Found = emails.stream()
                .anyMatch(e -> e.body().contains("Hello, " + customer1Username + "!"));
        boolean cust2Found = emails.stream()
                .anyMatch(e -> e.body().contains("Hello, " + customer2Username + "!"));

        assertThat(cust1Found).as("Customer1 should receive cancellation email").isTrue();
        assertThat(cust2Found).as("Customer2 should receive cancellation email").isTrue();

        for (EmailData email : emails) {
            assertThat(email.subject()).isEqualTo("Event cancellation notice");
            assertThat(email.body()).contains(EVENT_TITLE);
            assertThat(email.body()).contains("cancelled");
            assertThat(email.body()).contains("refunded automatically");
        }
    }

    // ── Selenium helpers ──────────────────────────────────────────────

    private void injectJwtAndNavigate(String jwt) throws Exception {
        driver.get(GATEWAY_URL);
        waitForPageLoad();

        String[] parts = jwt.split("\\.");
        String payload = new String(java.util.Base64.getUrlDecoder().decode(parts[1]), StandardCharsets.UTF_8);
        JsonNode claims = objectMapper.readTree(payload);
        String role = claims.has("role") ? claims.get("role").asText() : "CUSTOMER";
        String email = claims.has("email") ? claims.get("email").asText() : "";

        ((JavascriptExecutor) driver).executeScript(
                "localStorage.setItem('token', arguments[0]);" +
                "localStorage.setItem('userRole', arguments[1]);" +
                "localStorage.setItem('userEmail', arguments[2]);" +
                "App.handleRoute();",
                jwt, role, email);
        waitForPageLoad();
    }

    // ── HTTP helpers ──────────────────────────────────────────────────

    private String registerAndLogin(String role, String username, String email, String password) throws Exception {
        String registerBody = """
                {
                    "username": "%s",
                    "password": "%s",
                    "email": "%s",
                    "role": "%s"
                }
                """.formatted(username, password, email, role);

        HttpResponse<String> regResp = sendPost("/users/auth/register", registerBody, null);
        assertThat(regResp.statusCode()).as("Register %s should return 200".formatted(role)).isEqualTo(200);

        String loginBody = """
                {
                    "email": "%s",
                    "password": "%s"
                }
                """.formatted(email, password);

        HttpResponse<String> loginResp = sendPost("/users/auth/login", loginBody, null);
        assertThat(loginResp.statusCode()).as("Login %s should return 200".formatted(role)).isEqualTo(200);

        JsonNode loginJson = objectMapper.readTree(loginResp.body());
        return loginJson.get("jwt").asText();
    }

    private void buyTicket(String jwt, int evId) throws Exception {
        String body = """
                {
                    "eventId": %d,
                    "zone": "BASIC",
                    "price": 50.00,
                    "active": true
                }
                """.formatted(evId);

        HttpResponse<String> resp = sendPost("/booking/tickets", body, jwt);
        assertThat(resp.statusCode()).as("Ticket purchase should return 200").isEqualTo(200);

        JsonNode ticket = objectMapper.readTree(resp.body());
        assertThat(ticket.get("eventId").asInt()).isEqualTo(evId);
        assertThat(ticket.get("active").asBoolean()).isTrue();
    }

    private HttpResponse<String> sendPost(String path, String jsonBody, String jwt) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(GATEWAY_URL + path))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody));
        if (jwt != null) {
            builder.header("Authorization", "Bearer " + jwt);
        }
        return httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    private HttpResponse<String> sendGet(String path, String jwt) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(GATEWAY_URL + path))
                .GET();
        if (jwt != null) {
            builder.header("Authorization", "Bearer " + jwt);
        }
        return httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    private HttpResponse<String> sendDelete(String path, String jwt) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(GATEWAY_URL + path))
                .DELETE();
        if (jwt != null) {
            builder.header("Authorization", "Bearer " + jwt);
        }
        return httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    // ── Browser setup ─────────────────────────────────────────────────

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
        driver.manage().timeouts().pageLoadTimeout(Duration.ofSeconds(30));
        driver.manage().timeouts().scriptTimeout(Duration.ofSeconds(15));
    }

    private void waitForPageLoad() {
        try { Thread.sleep(2000); } catch (InterruptedException ignored) {}
    }

    // ── Docker Compose helpers ────────────────────────────────────────

    private static void startDockerCompose() throws Exception {
        ProcessBuilder pb = new ProcessBuilder(
                "docker", "compose", "up", "-d", "--build");
        pb.directory(Path.of("..").toFile());
        pb.redirectErrorStream(true);
        Process process = pb.start();
        String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        int exitCode = process.waitFor();
        if (exitCode != 0) {
            throw new RuntimeException("docker compose up failed:\n" + output);
        }
        waitForServicesHealthy();
    }

    private static void waitForServicesHealthy() throws Exception {
        System.out.println("Waiting for services to become healthy...");
        long deadline = System.currentTimeMillis() + 300_000L;

        while (System.currentTimeMillis() < deadline) {
            ProcessBuilder httpCheck = new ProcessBuilder(
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    GATEWAY_URL);
            httpCheck.redirectErrorStream(true);
            Process httpProcess = httpCheck.start();
            String httpCode = new String(httpProcess.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
            httpProcess.waitFor();

            if (httpCode.equals("200")) {
                System.out.println("Gateway is healthy!");
                Thread.sleep(5000);
                return;
            }

            System.out.print(".");
            Thread.sleep(5000);
        }
        throw new RuntimeException("Gateway did not become healthy within timeout");
    }

    private static void stopDockerCompose() {
        try {
            ProcessBuilder pb = new ProcessBuilder(
                    "docker", "compose", "down", "-v");
            pb.directory(Path.of("..").toFile());
            pb.redirectErrorStream(true);
            Process process = pb.start();
            process.waitFor();
            System.out.println("Docker Compose stopped.");
        } catch (Exception e) {
            System.err.println("Failed to stop Docker Compose: " + e.getMessage());
        }
    }

    // ── IMAP email helpers ────────────────────────────────────────────

    private List<EmailData> waitForEmails(String username, String password,
                                           String subjectContains, int expectedCount,
                                           int timeoutSeconds) throws Exception {
        long deadline = System.currentTimeMillis() + (timeoutSeconds * 1000L);

        while (System.currentTimeMillis() < deadline) {
            List<EmailData> found = searchEmails(username, password, subjectContains);
            if (found.size() >= expectedCount) {
                return found;
            }
            System.out.printf("Found %d/%d emails, waiting...%n", found.size(), expectedCount);
            Thread.sleep(5000);
        }
        return searchEmails(username, password, subjectContains);
    }

    private List<EmailData> searchEmails(String username, String password,
                                          String subjectContains) {
        Properties props = new Properties();
        props.put("mail.store.protocol", "imaps");
        props.put("mail.imaps.host", GMAIL_HOST);
        props.put("mail.imaps.port", String.valueOf(GMAIL_PORT));
        props.put("mail.imaps.ssl.enable", "true");
        props.put("mail.imaps.ssl.trust", GMAIL_HOST);

        Session session = Session.getInstance(props);
        Store store = null;
        Folder inbox = null;

        try {
            store = session.getStore("imaps");
            store.connect(GMAIL_HOST, username, password);

            inbox = store.getFolder("INBOX");
            inbox.open(Folder.READ_ONLY);

            long tenMinutesAgo = System.currentTimeMillis() - (10 * 60 * 1000L);
            Date since = new Date(tenMinutesAgo);
            jakarta.mail.search.ReceivedDateTerm dateTerm =
                    new jakarta.mail.search.ReceivedDateTerm(
                            jakarta.mail.search.ComparisonTerm.GE, since);
            jakarta.mail.search.SubjectTerm subjectTerm =
                    new jakarta.mail.search.SubjectTerm(subjectContains);
            jakarta.mail.search.AndTerm searchTerm =
                    new jakarta.mail.search.AndTerm(subjectTerm, dateTerm);

            Message[] messages = inbox.search(searchTerm);
            List<EmailData> results = new ArrayList<>();

            for (Message message : messages) {
                MimeMessage msg = (MimeMessage) message;
                String subject = msg.getSubject();
                String from = "";
                if (msg.getFrom() != null && msg.getFrom().length > 0) {
                    from = ((InternetAddress) msg.getFrom()[0]).getAddress();
                }
                String body = extractText(msg);
                results.add(new EmailData(subject, from, body));
            }
            return results;
        } catch (Exception e) {
            System.err.println("IMAP search error: " + e.getMessage());
            return List.of();
        } finally {
            try {
                if (inbox != null && inbox.isOpen()) inbox.close(true);
                if (store != null) store.close();
            } catch (Exception ignored) {}
        }
    }

    private String extractText(MimeMessage message) throws Exception {
        if (message.isMimeType("text/plain")) {
            return (String) message.getContent();
        }
        if (message.isMimeType("text/html")) {
            return (String) message.getContent();
        }
        if (message.isMimeType("multipart/*")) {
            MimeMultipart multipart = (MimeMultipart) message.getContent();
            for (int i = 0; i < multipart.getCount(); i++) {
                BodyPart bodyPart = multipart.getBodyPart(i);
                if (bodyPart.isMimeType("text/plain")) {
                    return (String) bodyPart.getContent();
                }
                if (bodyPart.isMimeType("text/html")) {
                    return (String) bodyPart.getContent();
                }
            }
        }
        return message.getContent().toString();
    }
}
