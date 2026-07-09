/* data-pipeline-and-processor
 *
 *
 *
 * Description:
 */
package udf

import org.apache.flink.table.functions.ScalarFunction

class FlinkCurrency2Country extends ScalarFunction{
  def eval(currency: String): String = {
    Currency2Country(currency)
  }
}

object FlinkCurrency2Country {
  val name = Currency2Country.name
}