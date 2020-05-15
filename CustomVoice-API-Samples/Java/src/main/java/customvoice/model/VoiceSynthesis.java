/*
 * Speech Services API v3.0-beta1
 */

package customvoice.model;

import java.util.Map;
import java.util.UUID;

import com.google.gson.annotations.SerializedName;

import org.threeten.bp.OffsetDateTime;

/**
 * VoiceSynthesis
 */
public class VoiceSynthesis {
  @SerializedName("id")
  private UUID id = null;

  @SerializedName("locale")
  private String locale = null;

  @SerializedName("resultsUrl")
  private String resultsUrl = null;

  @SerializedName("statusMessage")
  private String statusMessage = null;

  @SerializedName("createdDateTime")
  private OffsetDateTime createdDateTime = null;

  @SerializedName("lastActionDateTime")
  private OffsetDateTime lastActionDateTime = null;

  @SerializedName("status")
  private String status = null;

  @SerializedName("name")
  private String name = null;

  @SerializedName("description")
  private String description = null;

  @SerializedName("properties")
  private Map<String, String> properties = null;

  public UUID getId() {
    return id;
  }

  public void setId(UUID id) {
    this.id = id;
  }

  public String getLocale() {
    return locale;
  }

  public void setLocale(String locale) {
    this.locale = locale;
  }

  public String getResultsUrl() {
    return resultsUrl;
  }

  public void setResultsUrl(String resultsUrl) {
    this.resultsUrl = resultsUrl;
  }

  public String getStatusMessage() {
    return statusMessage;
  }

  public void setStatusMessage(String statusMessage) {
    this.statusMessage = statusMessage;
  }

  public OffsetDateTime getCreatedDateTime() {
    return createdDateTime;
  }

  public void setCreatedDateTime(OffsetDateTime createdDateTime) {
    this.createdDateTime = createdDateTime;
  }

  public OffsetDateTime getLastActionDateTime() {
    return lastActionDateTime;
  }

  public void setLastActionDateTime(OffsetDateTime lastActionDateTime) {
    this.lastActionDateTime = lastActionDateTime;
  }

  public String getStatus() {
    return status;
  }

  public void setStatus(String status) {
    this.status = status;
  }

  public String getName() {
    return name;
  }

  public void setName(String name) {
    this.name = name;
  }

  public String getDescription() {
    return description;
  }

  public void setDescription(String description) {
    this.description = description;
  }

  public Map<String, String> getProperties() {
    return properties;
  }

  public void setProperties(Map<String, String> properties) {
    this.properties = properties;
  }
}
