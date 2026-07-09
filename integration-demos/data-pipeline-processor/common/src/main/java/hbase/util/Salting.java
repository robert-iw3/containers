/* data-pipeline-and-processor
 *
 *
 *
 * Description:
 */
package hbase.util;

import java.math.BigInteger;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public class Salting {

    static MessageDigest md;

    static {
        try {
            md = MessageDigest.getInstance("MD5");
        } catch (NoSuchAlgorithmException e) {
            e.printStackTrace();
        }
    }

    private static String md5HashedString(String s) {
        byte[] digest = md.digest(s.getBytes());
        BigInteger bigInteger = new BigInteger(1, digest);
        return bigInteger.toString(16);
    }

    public static String getSaltedKey(String rowkey) {
        String hashedString = md5HashedString(rowkey);
        return hashedString.substring(hashedString.length()-2) + ":" + rowkey;
    }

    public static String getSaltedKey(String rowkey, int numRightChar) {
        String hashedString = md5HashedString(rowkey);
        return hashedString.substring(hashedString.length()-numRightChar) + ":" + rowkey;
    }
}