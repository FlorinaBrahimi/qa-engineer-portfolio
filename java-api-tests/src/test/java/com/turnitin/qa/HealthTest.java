package com.turnitin.qa;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

@Tag("smoke")
class HealthTest extends BaseApiTest {

  @Test
  @DisplayName("GET /health reports ok and names the storage backend")
  void healthIsOk() {
    given().spec(anonymous)
        .when().get("/health")
        .then().statusCode(200)
        .body("status", equalTo("ok"))
        .body("backend", isOneOf("MemoryStore", "DynamoStore"))
        .body("submissions", greaterThanOrEqualTo(0));
  }

  @Test
  @DisplayName("GET /api/openapi.json publishes the contract")
  void openApiIsPublished() {
    given().spec(anonymous)
        .when().get("/api/openapi.json")
        .then().statusCode(200)
        .body("openapi", startsWith("3."))
        .body("paths", hasKey("/api/submissions"))
        .body("paths", hasKey("/api/submissions/{id}"));
  }
}
