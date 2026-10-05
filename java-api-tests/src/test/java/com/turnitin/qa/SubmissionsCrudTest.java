package com.turnitin.qa;

import static io.restassured.module.jsv.JsonSchemaValidator.matchesJsonSchemaInClasspath;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.*;

import io.restassured.response.Response;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/** Create, read, list, delete, and the state transitions between them. */
@Tag("api")
@Tag("regression")
class SubmissionsCrudTest extends BaseApiTest {

  @AfterEach
  void cleanup() {
    client.cleanup();
  }

  @Test
  @Tag("smoke")
  @DisplayName("POST creates a submission whose body matches the JSON schema")
  void createMatchesSchema() {
    Map<String, Object> payload = Submissions.unique();

    client.create(payload)
        .then().statusCode(201)
        .body(matchesJsonSchemaInClasspath("schemas/submission.json"))
        .body("title", equalTo(payload.get("title")))
        .body("author", equalTo(payload.get("author")))
        .body("similarity_score", equalTo(0.0f))
        .body("status", equalTo("clear"));
  }

  @Test
  @DisplayName("GET by id returns exactly what POST returned")
  void getReturnsCreatedRecord() {
    Response created = client.create(Submissions.unique());
    String id = created.path("id");

    Response fetched = client.get(id);
    fetched.then().statusCode(200);
    assertThat(fetched.jsonPath().getMap("$"), equalTo(created.jsonPath().getMap("$")));
  }

  @Test
  @DisplayName("List contains the created submission with a correct count")
  void listContainsCreated() {
    String id = client.create(Submissions.unique()).path("id");

    client.list()
        .then().statusCode(200)
        .body("items.id", hasItem(id))
        .body("count", greaterThanOrEqualTo(1))
        .body("items.size()", equalTo(client.list().path("count")));
  }

  @Test
  @DisplayName("List is ordered newest first")
  void listIsNewestFirst() {
    String first = client.create(Submissions.unique()).path("id");
    String second = client.create(Submissions.unique()).path("id");

    java.util.List<String> ids = client.list().path("items.id");
    assertThat(ids.indexOf(second), lessThan(ids.indexOf(first)));
  }

  @Test
  @DisplayName("DELETE returns 204, then GET and DELETE return 404")
  void deleteThenGetIs404() {
    String id = client.create(Submissions.unique()).path("id");

    client.delete(id).then().statusCode(204);
    client.get(id).then().statusCode(404).body("error", equalTo("not_found"));
    client.delete(id).then().statusCode(404);
  }

  @Test
  @DisplayName("Unknown id returns 404 with the error schema")
  void unknownIdIs404() {
    client.get("does-not-exist")
        .then().statusCode(404)
        .body(matchesJsonSchemaInClasspath("schemas/error.json"));
  }

  @Test
  @DisplayName("Title and author are trimmed of surrounding whitespace")
  void inputIsTrimmed() {
    Map<String, Object> payload = Submissions.unique();
    payload.put("title", "  padded title  ");
    payload.put("author", "  padded author ");

    client.create(payload)
        .then().statusCode(201)
        .body("title", equalTo("padded title"))
        .body("author", equalTo("padded author"));
  }

  @Test
  @DisplayName("Word count matches the number of words submitted")
  void wordCountIsAccurate() {
    client.create(Submissions.unique("text", "one two three four five six seven eight nine ten eleven twelve"))
        .then().statusCode(201)
        .body("word_count", equalTo(12));
  }
}
