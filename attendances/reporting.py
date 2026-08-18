from datetime import datetime, time, timedelta

from django.utils import timezone


def format_duration(value):
    if value is None:
        return '0h 00m'
    minutes = int(value.total_seconds() // 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h {minutes:02d}m'


def _aware(day, value):
    dt = datetime.combine(day, value)
    return timezone.make_aware(dt, timezone.get_current_timezone())


def daily_summary(employee, day, attendance=None, logs=(), leave=None, holiday=None):
    events = sorted(logs, key=lambda item: (item.event_time, item.pk or 0))
    # Legacy rows remain reportable even if a migration was skipped or a row was imported later.
    if not events and attendance:
        synthetic = []
        if attendance.check_in:
            synthetic.append(('CHECK_IN', _aware(day, attendance.check_in)))
        if attendance.check_out:
            checkout = _aware(day, attendance.check_out)
            if attendance.check_in and attendance.check_out < attendance.check_in:
                checkout += timedelta(days=1)
            synthetic.append(('CHECK_OUT', checkout))
        normalized = synthetic
    else:
        normalized = [(event.event_type, timezone.localtime(event.event_time)) for event in events]

    check_ins = sum(kind == 'CHECK_IN' for kind, _ in normalized)
    check_outs = sum(kind == 'CHECK_OUT' for kind, _ in normalized)
    duration = timedelta()
    open_session = None
    invalid_sequence = False
    for kind, occurred_at in normalized:
        if kind == 'CHECK_IN':
            if open_session is not None:
                invalid_sequence = True
            else:
                open_session = occurred_at
        elif open_session is None:
            invalid_sequence = True
        else:
            if occurred_at >= open_session:
                duration += occurred_at - open_session
            else:
                invalid_sequence = True
            open_session = None

    incomplete = invalid_sequence or open_session is not None or check_ins != check_outs
    if normalized:
        status = 'Incomplete Attendance' if incomplete else (
            'Late' if attendance and attendance.status == 'LATE' else 'Present'
        )
    elif leave:
        status = 'On Leave'
    elif holiday:
        status = 'Holiday'
    else:
        status = 'Absent'
    return {
        'employee': employee, 'date': day, 'events': normalized,
        'first_check_in': next((at for kind, at in normalized if kind == 'CHECK_IN'), None),
        'last_check_out': next((at for kind, at in reversed(normalized) if kind == 'CHECK_OUT'), None),
        'check_in_count': check_ins, 'check_out_count': check_outs,
        'duration': duration, 'duration_display': format_duration(duration),
        'status': status, 'leave': leave, 'holiday': holiday,
        'info': leave.leave_type.name if leave else (holiday.name if holiday else ''),
    }


def date_span(start, end):
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)
