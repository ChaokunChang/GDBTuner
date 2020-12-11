import enum
import json

from ..template import Knob


class MySQLKnobs(object):
    def __init__(self, knobs_set, max_memory_size):
        # TODO: fetch default value from mysql
        if knobs_set == 'mini_knobs':
            # Obtained from MySQL 8.0 documentation
            knobs_path = f'data/mini_knobs.json'
            with open(knobs_path, 'r') as f:
                self.knobs_attrs = json.load(knobs_path)
        elif knobs_set == 'all_knobs':
            # Fetch from Ottertune
            knobs_path == f'data/mysql-80_knobs.json'
            with open(knobs_path, 'r') as f:
                all_knobs = json.load(knobs_path)

            class VarType(Enum):
                STRING = 1
                INTEGER = 2
                REAL = 3
                BOOL = 4
                ENUM = 5
                TIMESTAMP = 6

            def tunable(knob):
                attrs = knob['fields']
                if attrs['tunable'] and \
                    (attrs['vartype'] == VarType.INTEGER or \
                     attrs['vartype'] == VarType.REAL or \
                     attrs['vartype'] == VarType.BOOL):
                    return True

                return False

            type_map = {
                'STRING': 'str',
                'INTEGER': 'int',
                'REAL': 'float',
                'BOOL': 'bool',
                'ENUM': 'enum',
                'TIMESTAMP': 'timestamp',
            }

            # remove string and timestamp type knobs
            self.knobs_attrs = [x for x in all_knobs if tunable(x)]
            # convert to our format
            self.knobs_attrs = list(map(
                lambda x: {
                    "name": x['fields']['name'].replace('global.', ''),
                    "range": [x['fields']['minval'], x['fields']['maxval']],
                    "default": x['fields']['default'],
                    "type": type_map[VarType(x['fields']['vartype']).name],
                },
                self.knobs_attrs
            ))

        self.names = list(map(lambda x: x["name"], self.knobs_attrs))
        self.knobs = dict()

        # create dict of knobs for mysql
        for i, name in enumerate(self.names):
            self.knobs[name] = Knob(self.knobs_attrs[i])

        # bound by max_memory_size
        for name, knob in self.knobs:
            if knob.knob_type in ['int', 'float'] and \
                (name.endswith('size') or name.endswith('limit')):
                knob.max_value = min(knob.max_value, max_memory_size)

    @property
    def num_knobs(self):
        return len(self.names)

    def __getitem__(self, key):
        return self.knobs[key].value

    def apply_action(self, action):
        for i, name in enumerate(self.names):
            self.knobs[name].apply_action(action[i])

    def save(self, metrics, knob_file):
        knob_strs = []
        for name in self.knobs.keys():
            knob_strs.append('{}:{}'.format(name, self.knobs[name]))
        result_str = '{},{},{},'.format(metrics[0], metrics[1], metrics[2])
        knob_str = "#".join(knob_strs)
        result_str += knob_str

        with open(knob_file, 'a+') as f:
            f.write(result_str+'\n')


if __name__ == "__main__":
    from pprint import pprint
    import numpy as np

    max_memory_size = 4 * 1024 * 1024 * 1024
    mysql_knobs = MySQLKnobs('mini_knobs', max_memory_size)
    print(mysql_knobs.num_knobs)
    print(mysql_knobs)
    pprint(mysql_knobs.knobs)

    # generate random action
    for i in range(10):
        action = np.random.random(mysql_knobs.num_knobs)
        mysql_knobs.apply_action(action)
        pprint(mysql_knobs.knobs)

        for name in mysql_knobs.names:
            knob = mysql_knobs.knobs[name]
            assert(knob.min_value <= knob.value and knob.value <= knob.max_value)
