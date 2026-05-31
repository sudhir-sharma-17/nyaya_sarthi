import datetime
from typing import List, Dict, Any

class CourtScheduler:
    def generate_cause_list(self, cases: List[Dict[str, Any]], date: datetime.date) -> List[Dict[str, Any]]:
        """
        Generates an optimized cause list.
        Sorts by urgency, but ensures humanitarian cases are first.
        """
        # Sort: Humanitarian first, then by urgency score descending
        sorted_cases = sorted(
            cases,
            key=lambda x: (not x.get("humanitarian_flag", False), -x.get("urgency_score", 0))
        )
        
        cause_list = []
        current_time = datetime.datetime.combine(date, datetime.time(10, 30))
        
        for case in sorted_cases:
            cause_list.append({
                **case,
                "time": current_time.strftime("%I:%M %p"),
                "date": date.isoformat()
            })
            current_time += datetime.timedelta(minutes=30)
            
        return cause_list

court_scheduler = CourtScheduler()
