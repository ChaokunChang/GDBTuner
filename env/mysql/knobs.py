from ..template import Knob


class MySQLKnobs(object):
    def __init__(self):
        # TODO: fetch default value from mysql
        self.knobs_attrs = [
            {
                "name": 'table_open_cache',
                "range": [1, 10240],
                "default": 512,
                "type": "int"
            },
            {
                "name": 'innodb_buffer_pool_size',
                "range": [1048576, 34359738368],
                "default": 34359738368,
                "type": "int"
            },
            {
                "name": 'innodb_buffer_pool_instances',
                "range": [1, 64],
                "default": 8,
                "type": "int"
            },
            {
                "name": 'innodb_purge_threads',
                "range": [1, 32],
                "default": 1,
                "type": "int"
            },
            {
                "name": 'innodb_read_io_threads',
                "range": [1, 64],
                "default": 12,
                "type": "int"
            },
            {
                "name": 'innodb_write_io_threads',
                "range": [1, 64],
                "default": 12,
                "type": "int"
            },
        ]
        self.names = list(map(lambda x: x["name"], self.knobs_attrs))
        self.knobs = dict()

        # create dict of knobs for mysql
        for i, name in enumerate(self.names):
            self.knobs[name] = Knob(self.knobs_attrs[i])

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
        for name in self.knobs.names:
            knob_strs.append('{}:{}'.format(name, self.knobs[name]))
        result_str = '{},{},{},'.format(metrics[0], metrics[1], metrics[2])
        knob_str = "#".join(knob_strs)
        result_str += knob_str

        with open(knob_file, 'a+') as f:
            f.write(result_str+'\n')


if __name__ == "__main__":
    from pprint import pprint
    import numpy as np
    mysql_knobs = MySQLKnobs()
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
