/* data-pipeline-and-processor
 *
 *
 *
 * Description:
 */
package util

import com.fasterxml.jackson.databind.{DeserializationFeature, ObjectMapper}
import com.fasterxml.jackson.module.scala.DefaultScalaModule

class JacksonScalaObjectMapper extends Serializable {

  @transient lazy val objectMapper: ObjectMapper = {
    val m = new ObjectMapper()
    m.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
    m.registerModule(DefaultScalaModule)
  }


  def deserialize[T](json: String, clazz: Class[T]): T = {
    val output = objectMapper.readValue(json, clazz)
    output
  }

  def serialize(map: Any): String = {
    objectMapper.writeValueAsString(map)
  }

}