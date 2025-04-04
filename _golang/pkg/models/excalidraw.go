package models

// ExcalidrawDocument represents the root structure of an Excalidraw export
type ExcalidrawDocument struct {
	Type     string                 `json:"type"`
	Elements []ExcalidrawElement    `json:"elements"`
	Files    map[string]interface{} `json:"files"`
}

// ExcalidrawElement represents a generic element in Excalidraw
type ExcalidrawElement struct {
	ID                 string         `json:"id"`
	Type               string         `json:"type"`
	X                  float64        `json:"x"`
	Y                  float64        `json:"y"`
	Width              float64        `json:"width,omitempty"`
	Height             float64        `json:"height,omitempty"`
	Angle              float64        `json:"angle"`
	StrokeColor        string         `json:"strokeColor"`
	BackgroundColor    string         `json:"backgroundColor"`
	FillStyle          string         `json:"fillStyle"`
	StrokeWidth        float64        `json:"strokeWidth"`
	StrokeStyle        string         `json:"strokeStyle"`
	Roughness          float64        `json:"roughness"`
	Opacity            float64        `json:"opacity"`
	GroupIds           []string       `json:"groupIds"`
	FrameId            interface{}    `json:"frameId"`
	Roundness          Roundness      `json:"roundness"`
	Seed               int64          `json:"seed"`
	Version            int            `json:"version"`
	VersionNonce       int64          `json:"versionNonce"`
	IsDeleted          bool           `json:"isDeleted"`
	BoundElements      []BoundElement `json:"boundElements,omitempty"`
	Updated            int64          `json:"updated"`
	Link               interface{}    `json:"link"`
	Locked             bool           `json:"locked"`
	Points             [][]float64    `json:"points,omitempty"`
	LastCommittedPoint interface{}    `json:"lastCommittedPoint"`
	StartBinding       *Binding       `json:"startBinding,omitempty"`
	EndBinding         *Binding       `json:"endBinding,omitempty"`
	StartArrowhead     interface{}    `json:"startArrowhead"`
	EndArrowhead       string         `json:"endArrowhead,omitempty"`
	Text               string         `json:"text,omitempty"`
	FontSize           float64        `json:"fontSize,omitempty"`
	FontFamily         int            `json:"fontFamily,omitempty"`
	TextAlign          string         `json:"textAlign,omitempty"`
	VerticalAlign      string         `json:"verticalAlign,omitempty"`
	ContainerId        interface{}    `json:"containerId"`
	OriginalText       string         `json:"originalText,omitempty"`
	AutoResize         bool           `json:"autoResize,omitempty"`
	LineHeight         float64        `json:"lineHeight,omitempty"`
}

// Roundness represents the roundness configuration of an element
type Roundness struct {
	Type int `json:"type"`
}

// BoundElement represents a bound element in Excalidraw
type BoundElement struct {
	ID   string `json:"id"`
	Type string `json:"type"`
}

// Binding represents a binding configuration in Excalidraw
type Binding struct {
	ElementId  string      `json:"elementId"`
	Focus      float64     `json:"focus"`
	Gap        float64     `json:"gap"`
	FixedPoint interface{} `json:"fixedPoint"`
}
