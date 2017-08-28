from pytz import timezone
import datetime

def get_datetime_timezoned_from_timestamp(timestamp, timestamp_tz="Europe/Paris"):
    local_tz = timezone("Europe/Paris")
    date = get_localized_datetime(datetime.datetime.fromtimestamp(timestamp), timestamp_tz)
    return date.astimezone(local_tz)

def get_datetime_timezoned(datetime_to_convert, datetime_tz="UTC"):
    local_tz = timezone("Europe/Paris")
    date = get_localized_datetime(datetime_to_convert, datetime_tz)
    return date.astimezone(local_tz)


def get_localized_datetime(datetime_to_localize, tz):
    return timezone(tz).localize(datetime_to_localize)
