package com.turnitin.qa;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

import java.util.stream.Stream;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.MethodSource;

@Tag("security")
@Tag("regression")
class SecurityTest extends BaseApiTest {

  static Stream<Arguments> protectedEndpoints() {
    return Stream.of(
        Arguments.of("GET", "/api/submissions"),
        Arguments.of("POST", "/api/submissions"),
        Arguments.of("GET", "/api/submissions/any"),
        Arguments.of("DELETE", "/api/submissions/any"));
  }

  @ParameterizedTest(name = "{0} {1} without key")
  @MethodSource("protectedEndpoints")
  @DisplayName("Every API endpoint rejects a missing key with 401")
  void missingKeyIs401(String method, String path) {
    given().spec(anonymous).body("{}")
        .when().request(method, path)
        .then().statusCode(401)
        .body("error", equalTo("unauthorized"));
  }

  @ParameterizedTest(name = "{0} {1} with wrong key")
  @MethodSource("protectedEndpoints")
  @DisplayName("Every API endpoint rejects a wrong key with 401")
  void wrongKeyIs401(String method, String path) {
    given().spec(anonymous).header("X-API-Key", "not-the-key").body("{}")
        .when().request(method, path)
        .then().statusCode(401);
  }

  @ParameterizedTest(name = "{0}: {1}")
  @CsvSource({
    "X-Content-Type-Options, nosniff",
    "X-Frame-Options, DENY",
    "Referrer-Policy, no-referrer",
    "Cross-Origin-Opener-Policy, same-origin",
    "Cross-Origin-Resource-Policy, same-origin",
    "Cross-Origin-Embedder-Policy, require-corp",
    "Strict-Transport-Security, max-age=63072000; includeSubDomains",
    "Cache-Control, no-store"
  })
  @DisplayName("Hardening headers are present on every response")
  void hardeningHeadersPresent(String header, String expected) {
    given().spec(anonymous).when().get("/health").then().header(header, equalTo(expected));
    given().spec(anonymous).when().get("/").then().header(header, equalTo(expected));
  }

  @Test
  @DisplayName("Content Security Policy forbids framing, plugins and inline script")
  void contentSecurityPolicyIsRestrictive() {
    given().spec(anonymous).when().get("/").then()
        .header("Content-Security-Policy", allOf(
            containsString("default-src 'self'"), containsString("frame-ancestors 'none'"),
            containsString("object-src 'none'"), not(containsString("unsafe-inline"))));
  }

  @Test
  @DisplayName("Unknown API routes and wrong methods return JSON errors, not framework pages")
  void apiErrorsAreJson() {
    given().spec(authed).when().get("/api/does-not-exist").then().statusCode(404).body("error", equalTo("not_found"));
    given().spec(authed).when().put("/api/submissions").then().statusCode(405).body("error", equalTo("method_not_allowed"));
  }

  @Test
  @DisplayName("Server-owned properties cannot be set by the client (mass assignment)")
  void massAssignmentIsIgnored() {
    java.util.Map<String, Object> payload = Submissions.plagiarised();
    payload.put("id", "attacker-chosen");
    payload.put("status", "clear");
    payload.put("similarity_score", 0);
    String id = given().spec(authed).body(payload).when().post("/api/submissions").then().statusCode(201)
        .body("id", not(equalTo("attacker-chosen"))).body("status", equalTo("flagged")).body("similarity_score", equalTo(100.0f))
        .extract().path("id");
    given().spec(authed).delete("/api/submissions/" + id);
  }

  @Test
  @DisplayName("A cross-site form post is refused")
  void crossSiteFormPostIsRefused() {
    given().header("Sec-Fetch-Site", "cross-site").header("Origin", "https://evil.example")
        .contentType("application/x-www-form-urlencoded")
        .formParam("title", "Forged").formParam("author", "x").formParam("text", "forged by another website entirely")
        .redirects().follow(false)
        .when().post("/submit").then().statusCode(403);
  }

  @Test
  @DisplayName("Error responses do not leak stack traces or server internals")
  void errorsDoNotLeakInternals() {
    given().spec(anonymous).when().get("/api/submissions")
        .then().statusCode(401)
        .body(not(containsString("Traceback")))
        .body(not(containsString("flask")))
        .header("Server", not(containsString("Werkzeug")));
  }
}
