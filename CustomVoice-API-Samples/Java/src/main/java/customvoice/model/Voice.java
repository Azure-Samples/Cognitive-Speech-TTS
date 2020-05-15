/*
 * Speech Services API v3.0-beta1
 */

package customvoice.model;

import java.util.UUID;

import com.google.gson.annotations.SerializedName;

/**
 * Voice
 */
public class Voice {
  @SerializedName("locale")
  private String locale = null;

  @SerializedName("name")
  private String name = null;

  @SerializedName("id")
  private UUID id = null;

  @SerializedName("gender")
  private String gender = null;

  @SerializedName("isPublicVoice")
  private Boolean isPublicVoice = null;

  public String getLocale() {
    return locale;
  }

  public void setLocale(String locale) {
    this.locale = locale;
  }

  public String getName() {
    return name;
  }

  public void setName(String name) {
    this.name = name;
  }

  public UUID getId() {
    return id;
  }

  public void setId(UUID id) {
    this.id = id;
  }

  public String getGender() {
    return gender;
  }

  public void setGender(String gender) {
    this.gender = gender;
  }

  public Boolean isIsPublicVoice() {
    return isPublicVoice;
  }

  public void setIsPublicVoice(Boolean isPublicVoice) {
    this.isPublicVoice = isPublicVoice;
  }
}
