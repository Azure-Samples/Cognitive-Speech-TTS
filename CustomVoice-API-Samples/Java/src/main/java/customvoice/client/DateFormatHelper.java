package customvoice.client;

import java.text.DateFormat;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;

public class DateFormatHelper {
    static DateFormat timeFormatter = new SimpleDateFormat("yyyy-MM-dd HH:mm");
    static DateFormat longTimeFormatter = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
    static DateFormat dateFormatter = new SimpleDateFormat("yyyy-MM-dd");

    public static Date parseToDate(String dateStr) throws ParseException {
        if (dateStr.length() <= 10) {
            return dateFormatter.parse(dateStr);
        } else if (dateStr.length() <= 16) {
            return timeFormatter.parse(dateStr);
        }
        return longTimeFormatter.parse(dateStr);
    }

    public static String parseToString(Date date) throws ParseException {
        return longTimeFormatter.format(date);
    }
}