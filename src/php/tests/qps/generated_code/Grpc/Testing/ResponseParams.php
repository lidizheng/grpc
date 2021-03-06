<?php
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: src/proto/grpc/testing/echo_messages.proto

namespace Grpc\Testing;

use Google\Protobuf\Internal\GPBType;
use Google\Protobuf\Internal\RepeatedField;
use Google\Protobuf\Internal\GPBUtil;

/**
 * Generated from protobuf message <code>grpc.testing.ResponseParams</code>
 */
class ResponseParams extends \Google\Protobuf\Internal\Message
{
    /**
     * Generated from protobuf field <code>int64 request_deadline = 1;</code>
     */
    protected $request_deadline = 0;
    /**
     * Generated from protobuf field <code>string host = 2;</code>
     */
    protected $host = '';
    /**
     * Generated from protobuf field <code>string peer = 3;</code>
     */
    protected $peer = '';

    /**
     * Constructor.
     *
     * @param array $data {
     *     Optional. Data for populating the Message object.
     *
     *     @type int|string $request_deadline
     *     @type string $host
     *     @type string $peer
     * }
     */
    public function __construct($data = NULL) {
        \GPBMetadata\Src\Proto\Grpc\Testing\EchoMessages::initOnce();
        parent::__construct($data);
    }

    /**
     * Generated from protobuf field <code>int64 request_deadline = 1;</code>
     * @return int|string
     */
    public function getRequestDeadline()
    {
        return $this->request_deadline;
    }

    /**
     * Generated from protobuf field <code>int64 request_deadline = 1;</code>
     * @param int|string $var
     * @return $this
     */
    public function setRequestDeadline($var)
    {
        GPBUtil::checkInt64($var);
        $this->request_deadline = $var;

        return $this;
    }

    /**
     * Generated from protobuf field <code>string host = 2;</code>
     * @return string
     */
    public function getHost()
    {
        return $this->host;
    }

    /**
     * Generated from protobuf field <code>string host = 2;</code>
     * @param string $var
     * @return $this
     */
    public function setHost($var)
    {
        GPBUtil::checkString($var, True);
        $this->host = $var;

        return $this;
    }

    /**
     * Generated from protobuf field <code>string peer = 3;</code>
     * @return string
     */
    public function getPeer()
    {
        return $this->peer;
    }

    /**
     * Generated from protobuf field <code>string peer = 3;</code>
     * @param string $var
     * @return $this
     */
    public function setPeer($var)
    {
        GPBUtil::checkString($var, True);
        $this->peer = $var;

        return $this;
    }

}

