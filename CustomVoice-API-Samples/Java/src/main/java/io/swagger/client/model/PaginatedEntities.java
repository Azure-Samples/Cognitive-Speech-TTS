package io.swagger.client.model;

import java.util.Objects;
import java.util.Arrays;
import java.util.List;

import com.google.gson.TypeAdapter;
import com.google.gson.annotations.JsonAdapter;
import com.google.gson.annotations.SerializedName;
import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonWriter;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import java.io.IOException;
import java.util.UUID;

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
}
