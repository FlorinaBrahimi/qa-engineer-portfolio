package com.turnitin.qa;

import static io.restassured.module.jsv.JsonSchemaValidator.matchesJsonSchemaInClasspath;
import static org.hamcrest.Matchers.*;

import java.util.Map;
import java.util.stream.Stream;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;

/** Input validation: boundaries, missing fields, malformed bodies. */
@Tag("api")
@Tag("regression")
class SubmissionsValidationTest extends BaseApiTest {

  @AfterEach
  void cleanup() {
    client.cleanup();
  }

  static Stream<Arguments> invalidFields() {
    return Stream.of(
        Arguments.of("title", "", "title is required"),
        Arguments.of("title", "   ", "title is required"),
        Arguments.of("title", "t".repeat(201), "title must be 200 characters or fewer"),
        Arguments.of("author", "", "author is required"),
        Arguments.of("author", "a".repeat(201), "author must be 200 characters or fewer"),
        Arguments.of("text", "", "text must be at least 20 characters"),
        Arguments.of("text", "nineteen chars long", "text must be at least 20 characters"),
        Arguments.of("text", "x".repeat(20_001), "text must be at most 20000 characters"));
  }

  @ParameterizedTest(name = "{0} = {1} -> {2}")
  @MethodSource("invalidFields")
  @DisplayName("Invalid field returns 400 naming the field and reason")
  void invalidFieldIsRejected(String field, String value, String expectedMessage) {
    String shown = value.length() > 30 ? value.substring(0, 30) + "..." : value;
    client.create(Submissions.unique(field, value))
        .then().statusCode(400)
        .body(matchesJsonSchemaInClasspath("schemas/error.json"))
        .body("error", equalTo("validation_failed"))
        .body("fields." + field, equalTo(expectedMessage));
  }

  static Stream<Arguments> boundaries() {
    return Stream.of(
        Arguments.of("title", "t".repeat(200), 201),
        Arguments.of("text", "x".repeat(20), 201),
        Arguments.of("text", "x".repeat(20_000), 201));
  }

  @ParameterizedTest(name = "{0} at boundary length -> {2}")
  @MethodSource("boundaries")
  @DisplayName("Values exactly at the boundary are accepted")
  void boundaryValuesAccepted(String field, String value, int expectedStatus) {
    client.create(Submissions.unique(field, value)).then().statusCode(expectedStatus);
  }

  @ParameterizedTest(name = "body {0}")
  @ValueSource(strings = {"null", "[]", "\"string\"", "42", "{not json", ""})
  @DisplayName("Non-object or malformed JSON body returns 400")
  void nonObjectBodyIsRejected(String body) {
    client.createRaw(body).then().statusCode(400);
  }

  @ParameterizedTest(name = "missing {0}")
  @ValueSource(strings = {"title", "author", "text"})
  @DisplayName("A missing required field is reported by name")
  void missingFieldIsReported(String field) {
    Map<String, Object> payload = Submissions.unique();
    payload.remove(field);
    client.create(payload)
        .then().statusCode(400)
        .body("fields", hasKey(field));
  }

  @ParameterizedTest(name = "title {0}")
  @ValueSource(strings = {"<script>alert(1)</script>", "' OR 1=1 --", "{{ 7 * 7 }}", "Ünïcödé ✓ 日本語"})
  @DisplayName("Hostile or non-ASCII input is stored verbatim, never executed or mangled")
  void hostileInputRoundTrips(String title) {
    client.create(Submissions.unique("title", title))
        .then().statusCode(201)
        .body("title", equalTo(title));
  }
}
