package converter

import (
	"encoding/json"
	"os"
	"strings"
	"testing"

	"github.com/kyleking/excalidraw2plantuml/pkg/models"
)

func TestConverter_Convert(t *testing.T) {
	// Sample Excalidraw document based on the provided JSON
	doc := &models.ExcalidrawDocument{
		Type: "excalidraw/clipboard",
		Elements: []models.ExcalidrawElement{
			{
				ID:     "MAZsWO29",
				Type:   "rectangle",
				X:      5.4683066319616955,
				Y:      130.9780767679731,
				Width:  1200, // Large rectangle for system boundary
				Height: 800,
				BoundElements: []models.BoundElement{
					{
						ID:   "text1",
						Type: "text",
					},
				},
			},
			{
				ID:     "Bq7ET4JQ",
				Type:   "rectangle",
				X:      1251.939692781465,
				Y:      42.762730505554146,
				Width:  549.9138468306633,
				Height: 549.9138468306633,
				BoundElements: []models.BoundElement{
					{
						ID:   "text2",
						Type: "text",
					},
				},
			},
			{
				ID:     "R3tckAe0",
				Type:   "rectangle",
				X:      1251.939692781465,
				Y:      42.762730505554146,
				Width:  549.9138468306633,
				Height: 549.9138468306633,
				BoundElements: []models.BoundElement{
					{
						ID:   "text3",
						Type: "text",
					},
				},
			},
			{
				ID:            "text1",
				Type:          "text",
				X:             85.66407596143335,
				Y:             305.11746159768313,
				Text:          "Moat",
				FontSize:      84.15661546357732,
				FontFamily:    5,
				TextAlign:     "left",
				VerticalAlign: "top",
			},
			{
				ID:            "text2",
				Type:          "text",
				X:             1394.8572223657081,
				Y:             181.02382322421656,
				Text:          "Right Box",
				FontSize:      97.57288749400271,
				FontFamily:    5,
				TextAlign:     "left",
				VerticalAlign: "top",
			},
			{
				ID:            "text3",
				Type:          "text",
				X:             1394.8572223657081,
				Y:             181.02382322421656,
				Text:          "Left Box",
				FontSize:      97.57288749400271,
				FontFamily:    5,
				TextAlign:     "left",
				VerticalAlign: "top",
			},
			{
				ID:     "arrow1",
				Type:   "arrow",
				X:      562.2560765480082,
				Y:      330.3218462440884,
				Points: [][]float64{{0, 0}, {730.9271547457563, -11.456538475638808}},
				StartBinding: &models.Binding{
					ElementId: "Bq7ET4JQ",
					Focus:     -0.12956730769230793,
					Gap:       22.913076951277617,
				},
				EndBinding: &models.Binding{
					ElementId: "R3tckAe0",
					Focus:     -0.12956730769230793,
					Gap:       22.913076951277617,
				},
			},
		},
	}

	conv := NewConverter()
	result := conv.Convert(doc)

	// Verify the output contains expected PlantUML elements
	expectedElements := []string{
		"@startuml",
		"!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml",
		"LAYOUT_WITH_LEGEND()",
		"System_Boundary(MAZsWO29, \"Moat\")",
		"    Container(Element_Bq7ET4JQ, \"Right Box\")",
		"    Container(Element_R3tckAe0, \"Left Box\")",
		"Rel(Element_Bq7ET4JQ, Element_R3tckAe0, \"\")",
		"@enduml",
	}

	for _, expected := range expectedElements {
		if !strings.Contains(result, expected) {
			t.Errorf("Expected output to contain '%s', but it didn't", expected)
		}
	}
}

func TestConverter_convertRectangle(t *testing.T) {
	conv := NewConverter()

	// Test regular container
	elem := &models.ExcalidrawElement{
		ID:     "test12345", // Make sure ID is at least 8 characters
		Type:   "rectangle",
		Width:  100,
		Height: 100,
		Text:   "Test Box",
	}

	result := conv.convertRectangle(elem)
	expected := "    Container(Element_test1234, \"Test Box\")\n"
	if result != expected {
		t.Errorf("Expected '%s', got '%s'", expected, result)
	}
}

func TestConverter_convertText(t *testing.T) {
	conv := NewConverter()
	elem := &models.ExcalidrawElement{
		ID:   "test12345", // Make sure ID is at least 8 characters
		Type: "text",
		Text: "Test Note",
	}

	result := conv.convertText(elem)
	expected := "note \"Test Note\" as Note_test1234\n"
	if result != expected {
		t.Errorf("Expected '%s', got '%s'", expected, result)
	}
}

func TestConverter_convertArrow(t *testing.T) {
	conv := NewConverter()
	elem := &models.ExcalidrawElement{
		ID:     "test12345", // Make sure ID is at least 8 characters
		Type:   "arrow",
		Points: [][]float64{{0, 0}, {100, 0}},
		StartBinding: &models.Binding{
			ElementId: "start12345",
		},
		EndBinding: &models.Binding{
			ElementId: "end12345",
		},
	}

	// Add elements to the converter's map
	conv.elements = map[string]*models.ExcalidrawElement{
		"start12345": {
			ID:   "start12345",
			Type: "rectangle",
			Text: "Start",
		},
		"end12345": {
			ID:   "end12345",
			Type: "rectangle",
			Text: "End",
		},
	}

	result := conv.convertArrow(elem)
	expected := "Rel(Element_start123, Element_end12345, \"\")\n"
	if result != expected {
		t.Errorf("Expected '%s', got '%s'", expected, result)
	}
}

func TestConverter_ConvertComplexDiagram(t *testing.T) {
	// Load the complex diagram from excalidraw.pretty.json
	jsonData, err := os.ReadFile("../../excalidraw.pretty.json")
	if err != nil {
		t.Fatalf("Failed to read excalidraw.pretty.json: %v", err)
	}

	var doc models.ExcalidrawDocument
	if err := json.Unmarshal(jsonData, &doc); err != nil {
		t.Fatalf("Failed to unmarshal excalidraw.pretty.json: %v", err)
	}

	conv := NewConverter()
	result := conv.Convert(&doc)

	// Verify the output contains expected PlantUML elements
	expectedElements := []string{
		"@startuml",
		"!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml",
		"LAYOUT_WITH_LEGEND()",
		"Person(Element_GYxi3kGD, \"User\")",
		"System_Boundary(Element_FzRoP4BP, \"AWS Cloud\")",
		"System_Boundary(Element_66fHx-01, \"EKS\")",
		"Container(Element_4PrGM9vp, \"Study Companion\")",
		"Container(Element__KSwFqmd, \"Ingestor\")",
		"ComponentDb(Element_fjrWPeNR, \"Database\")",
		"Container(Element_NS92iwVt, \"Event Bridge\")",
		"Container(Element_WepoXBEb, \"Assets\")",
		"Rel(Element_GYxi3kGD, Element_4PrGM9vp, \"Queries Services\")",
		"Rel(Element_4PrGM9vp, Element_fjrWPeNR, \"Saves\")",
		"Rel(Element_NS92iwVt, Element__KSwFqmd, \"\")",
		"Rel(Element__KSwFqmd, Element_WepoXBEb, \"Writes\")",
		"Rel(Element_4PrGM9vp, Element_WepoXBEb, \"Reads\")",
		"@enduml",
	}

	for _, expected := range expectedElements {
		if !strings.Contains(result, expected) {
			t.Errorf("Expected output to contain '%s', but it didn't", expected)
		}
	}

	// Write the result to a file for inspection
	if err := os.WriteFile("../../complex_diagram.puml", []byte(result), 0644); err != nil {
		t.Errorf("Failed to write complex_diagram.puml: %v", err)
	}
}
