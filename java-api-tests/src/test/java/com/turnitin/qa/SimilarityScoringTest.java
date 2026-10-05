package com.turnitin.qa;

import static org.hamcrest.Matchers.*;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/** The business rule that matters most: scoring and the 25% flag threshold. */
@Tag("api")
@Tag("regression")
class SimilarityScoringTest extends BaseApiTest {

  @AfterEach
  void cleanup() {
    client.cleanup();
  }

  @Test
  @DisplayName("Text copied verbatim from the corpus scores 100 and is flagged")
  void copiedTextIsFlagged() {
    client.create(Submissions.plagiarised())
        .then().statusCode(201)
        .body("similarity_score", equalTo(100.0f))
        .body("status", equalTo("flagged"));
  }

  @Test
  @DisplayName("Original text scores 0 and is clear")
  void originalTextIsClear() {
    client.create(Submissions.unique())
        .then().statusCode(201)
        .body("similarity_score", equalTo(0.0f))
        .body("status", equalTo("clear"));
  }

  @Test
  @DisplayName("Partially copied text scores strictly between 0 and 100")
  void partialOverlapScoresBetweenBounds() {
    client.create(Submissions.partialOverlap())
        .then().statusCode(201)
        .body("similarity_score", allOf(greaterThan(0.0f), lessThan(100.0f)));
  }

  @Test
  @DisplayName("Scoring ignores case and punctuation")
  void scoringIsCaseAndPunctuationInsensitive() {
    client.create(Submissions.unique("text",
            "THE MITOCHONDRIA, is the POWERHOUSE of the cell; and produces energy through respiration!"))
        .then().statusCode(201)
        .body("similarity_score", equalTo(100.0f));
  }
}
