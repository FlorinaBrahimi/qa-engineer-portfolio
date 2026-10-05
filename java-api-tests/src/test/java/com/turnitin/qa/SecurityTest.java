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
    "Content-Security-Policy, default-src 'self'",
    "Referrer-Policy, no-referrer"
  })
  @DisplayName("Hardening headers are present on every response")
  void hardeningHeadersPresent(String header, String expected) {
    given().spec(anonymous).when().get("/health").then().header(header, equalTo(expected));
    given().spec(anonymous).when().get("/").then().header(header, equalTo(expected));
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
