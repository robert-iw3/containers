import React, { useState, useCallback } from "react";
import { Handle } from "@xyflow/react";

const nodeStyle = {
  padding: "12px",
  border: "2px solid #4a4a4a",
  borderRadius: "8px",
  background: "#2a2a2a",
  color: "#ffffff",
  width: "220px",
  boxShadow: "0 2px 4px rgba(0, 0, 0, 0.2)",
  transition: "all 0.2s ease",
  overflow: "hidden",
};

const inputStyle = {
  margin: "8px 0",
  padding: "8px 12px",
  width: "calc(100% - 16px)",
  backgroundColor: "#1a1a1a",
  color: "#ffffff",
  border: "1px solid #3d3d3d",
  borderRadius: "6px",
  boxSizing: "border-box",
  fontSize: "14px",
  transition: "all 0.2s ease",
};

const NodeContent = ({ type, data, onChange, placeholder }) => {
  const [localData, setLocalData] = useState(data);
  const [error, setError] = useState(null);
  const [isFocused, setIsFocused] = useState(false);

  const handleChange = useCallback(
    (e) => {
      const value = e.target.value;
      const newData = { ...localData, [e.target.name]: value };

      // Validate input based on node type
      const nodeConfig = NodeTypes[type];
      const isValid = nodeConfig.validate ? nodeConfig.validate(value) : true;
      setError(isValid ? null : 'Invalid format');

      setLocalData(newData);
      onChange(newData);
    },
    [localData, onChange, type],
  );

  const getNodeTypeColor = (type) => {
    switch (type) {
      case 'sourceNode': return '#4CAF50';
      case 'destinationNode': return '#2196F3';
      case 'actionNode': return '#FF9800';
      case 'tagNode': return '#9C27B0';
      default: return '#4a4a4a';
    }
  };

  return (
    <div>
      <div style={{
        fontSize: "14px",
        fontWeight: "600",
        marginBottom: "8px",
        color: getNodeTypeColor(type),
        textTransform: "uppercase",
        letterSpacing: "0.5px"
      }}>
        {type.replace('Node', '')}
      </div>
      <input
        style={{
          ...inputStyle,
          borderColor: error ? '#ff4444' : isFocused ? getNodeTypeColor(type) : '#3d3d3d',
          boxShadow: isFocused ? `0 0 0 2px ${getNodeTypeColor(type)}33` : 'none'
        }}
        name="value"
        value={localData.value || ""}
        onChange={handleChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        placeholder={placeholder}
      />
      {error && (
        <div style={{
          color: '#ff4444',
          fontSize: '12px',
          marginTop: '4px',
          padding: '4px 8px',
          backgroundColor: '#ff444411',
          borderRadius: '4px'
        }}>
          {error}
        </div>
      )}
    </div>
  );
};

const NodeTypes = {
  sourceNode: {
    placeholder: "user@example.com or group:name",
    width: "220px",
    handleConfig: [
      { type: "source", position: "right", style: { right: -6 } }
    ],
    validate: (value) => {
      return value.match(/^([a-zA-Z0-9_.-]+@[a-zA-Z0-9_.-]+|group:[a-zA-Z0-9_-]+|tag:[a-zA-Z0-9_-]+)$/);
    }
  },
  destinationNode: {
    placeholder: "192.168.1.1:80",
    width: "180px",
    handleConfig: [
      { type: "target", position: "left", style: { left: -6 } }
    ],
    validate: (value) => {
      return value.match(/^[0-9.:/*]+$/);
    }
  },
  actionNode: {
    placeholder: "accept or deny",
    width: "180px",
    handleConfig: [
      { type: "target", position: "left", style: { left: -6 } },
      { type: "source", position: "right", style: { right: -6 } }
    ],
    validate: (value) => {
      return ["accept", "deny"].includes(value.toLowerCase());
    }
  },
  tagNode: {
    placeholder: "tag:name",
    width: "180px",
    handleConfig: [
      { type: "target", position: "left", style: { left: -6 } },
      { type: "source", position: "right", style: { right: -6 } }
    ],
    validate: (value) => {
      return value.match(/^tag:[a-zA-Z0-9_-]+$/);
    }
  }
};

const BaseNode = ({ type, data, isConnectable, style = {} }) => {
  const nodeConfig = NodeTypes[type];

  return (
    <div style={{
      ...nodeStyle,
      ...style,
      width: nodeConfig.width
    }}>
      {nodeConfig.handleConfig.map(({ type, position }) => (
        <Handle
          key={`${type}-${position}`}
          type={type}
          position={position}
          isConnectable={isConnectable}
        />
      ))}
      <NodeContent
        type={type}
        data={data}
        onChange={data.onChange}
        placeholder={nodeConfig.placeholder}
      />
    </div>
  );
};

export const SourceNode = (props) => <BaseNode type="sourceNode" {...props} />;
export const DestinationNode = (props) => (
  <BaseNode
    type="destinationNode"
    style={{ fontSize: "0.8em", padding: "5px" }}
    {...props}
  />
);
export const ActionNode = (props) => <BaseNode type="actionNode" {...props} />;
export const TagNode = (props) => <BaseNode type="tagNode" {...props} />;
