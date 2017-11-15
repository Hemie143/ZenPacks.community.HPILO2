from . import schema


class HPILO2Chassis(schema.HPILO2Chassis):
    """HPChassis"""

    def get_cpu_count(self):
        return len(self.hpilo2processors())

