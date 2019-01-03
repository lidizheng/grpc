import string
import grpc_channelz.v1.channelz_pb2 as _channelz_pb2

_EMPTY_TIME_STR = '1970-01-01T00:00:00Z'


def _sanitize(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _Renderer(string.Formatter):

    def format_field(self, value, format_spec):  # pylint: disable=too-many-return-statements
        if format_spec.startswith('loop'):
            template = format_spec.partition(':')[-1]
            return ''.join([self.format(template, item=item) for item in value])
        elif format_spec == 'call':
            return value()
        elif format_spec == 'state':
            return _channelz_pb2.ChannelConnectivityState.State.Name(
                value.state)
        elif format_spec == 'timestamp':
            json_str = value.ToJsonString()
            return 'N/A' if json_str == _EMPTY_TIME_STR else json_str
        elif format_spec == 'address':
            if value.HasField('tcpip_address'):
                return '%s:%d' % (value.tcpip_address.ip_address,
                                  value.tcpip_address.port)
            elif value.HasField('uds_address'):
                return value.uds_address.filename
            elif value.HasField('other_address'):
                return value.other_address.name
            else:
                return 'N/A'
        elif format_spec == 'sanitized':
            return super(_Renderer, self).format_field(value, '')
        else:
            return _sanitize(
                super(_Renderer, self).format_field(value, format_spec))
