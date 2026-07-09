/* data-pipeline-and-processor
 *
 *
 *
 * Description:
 */
package util

object ConversionHelper {
  def getMilliSecond(time: Long): Long = {
    if ((time & Const.SECOND_MASK) != 0) time else time * 1000L
  }
}