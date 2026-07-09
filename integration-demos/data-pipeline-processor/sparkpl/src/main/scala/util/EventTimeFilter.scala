/* data-pipeline-and-processor
 *
 *
 *
 * Description:
 */
package util

import org.apache.spark.sql.Row
import util.ConversionHelper.getMilliSecond

class EventTimeFilter(eventTimeFieldName: String) extends (Row => Boolean) with Serializable {

  import TimeFilter._

  override def apply(row: Row): Boolean = {
    val eventTime = getMilliSecond(row.getAs(eventTimeFieldName).toString.toLong)
    checkWithinProcessingWindow(eventTime)
  }

}