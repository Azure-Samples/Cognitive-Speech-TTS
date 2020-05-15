package customvoice.model;

import java.util.List;

import com.google.gson.annotations.SerializedName;

/**
 * PaginatedEntities
 */
public class PaginatedEntities<T> {
  @SerializedName("values")
  private List<T> values = null;

  @SerializedName("nextLink")
  private String nextLink = null;

  public List<T> getValues() {
    return values;
  }

  public void setValues(List<T> values) {
    this.values = values;
  }

  public String getNextLink() {
    return nextLink;
  }

  public void setNextLink(String nextLink) {
    this.nextLink = nextLink;
  }
}
