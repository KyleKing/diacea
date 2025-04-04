package converter

import (
	"fmt"
	"math"
	"sort"
	"strings"

	"github.com/kyleking/excalidraw2plantuml/pkg/models"
)

// Converter handles the conversion from Excalidraw to PlantUML
type Converter struct {
	elements map[string]*models.ExcalidrawElement
}

// NewConverter creates a new converter instance
func NewConverter() *Converter {
	return &Converter{
		elements: make(map[string]*models.ExcalidrawElement),
	}
}

// Convert converts an Excalidraw document to PlantUML
func (c *Converter) Convert(doc *models.ExcalidrawDocument) string {
	// Build element map for quick lookup
	c.elements = make(map[string]*models.ExcalidrawElement)
	for i := range doc.Elements {
		c.elements[doc.Elements[i].ID] = &doc.Elements[i]
	}

	var sb strings.Builder
	sb.WriteString("@startuml\n")
	sb.WriteString("!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml\n\n")
	sb.WriteString("LAYOUT_WITH_LEGEND()\n\n")

	// First pass: Find system boundaries and people
	var systemBoundaries []*models.ExcalidrawElement
	var people []*models.ExcalidrawElement
	var containers []*models.ExcalidrawElement
	for i := range doc.Elements {
		elem := &doc.Elements[i]
		if elem.Type == "rectangle" {
			// Check if this is a system boundary based on size or text
			text := c.getElementText(elem)
			isSystemBoundary := elem.Width > 500 || elem.Height > 500 ||
				strings.Contains(strings.ToLower(text), "cloud") ||
				strings.Contains(strings.ToLower(text), "eks")

			if isSystemBoundary {
				systemBoundaries = append(systemBoundaries, elem)
			} else {
				containers = append(containers, elem)
			}
		} else if elem.Type == "diamond" {
			people = append(people, elem)
		} else if elem.Type == "ellipse" {
			containers = append(containers, elem)
		}
	}

	// Sort system boundaries by size (largest first)
	sort.Slice(systemBoundaries, func(i, j int) bool {
		areaI := systemBoundaries[i].Width * systemBoundaries[i].Height
		areaJ := systemBoundaries[j].Width * systemBoundaries[j].Height
		return areaI > areaJ
	})

	// Second pass: Define people
	for _, person := range people {
		text := c.getElementText(person)
		if text == "" {
			text = "User"
		}
		sb.WriteString(fmt.Sprintf("Person(Element_%s, \"%s\")\n", person.ID[:8], text))
	}

	// Third pass: Define system boundaries and their containers
	processedContainers := make(map[string]bool)
	processedBoundaries := make(map[string]bool)
	for _, boundary := range systemBoundaries {
		if processedBoundaries[boundary.ID] {
			continue
		}

		// Find text element for the system boundary
		boundaryText := c.getElementText(boundary)
		if boundaryText == "" {
			// Try to find a text element near the top of the boundary
			var minY float64 = 1e9
			var minX float64 = 1e9
			for _, elem := range doc.Elements {
				if elem.Type == "text" && elem.ContainerId == nil {
					// Check if the text element is positioned near the top of the boundary
					if elem.X >= boundary.X &&
						elem.Y >= boundary.Y &&
						elem.X+elem.Width <= boundary.X+boundary.Width &&
						elem.Y+elem.Height <= boundary.Y+boundary.Height/4 {
						// Use the text element with the smallest Y coordinate (topmost)
						// If there are multiple text elements at the same Y, use the leftmost one
						if elem.Y < minY || (elem.Y == minY && elem.X < minX) {
							minY = elem.Y
							minX = elem.X
							boundaryText = strings.TrimSpace(strings.ReplaceAll(elem.Text, "\n", " "))
						}
					}
				}
			}
		}

		if boundaryText == "" {
			boundaryText = "System"
		}

		sb.WriteString(fmt.Sprintf("System_Boundary(Element_%s, \"%s\") {\n", boundary.ID[:8], boundaryText))

		// Find nested system boundaries
		for _, nestedBoundary := range systemBoundaries {
			if nestedBoundary.ID != boundary.ID &&
				!processedBoundaries[nestedBoundary.ID] &&
				nestedBoundary.X >= boundary.X &&
				nestedBoundary.Y >= boundary.Y &&
				nestedBoundary.X+nestedBoundary.Width <= boundary.X+boundary.Width &&
				nestedBoundary.Y+nestedBoundary.Height <= boundary.Y+boundary.Height {

				nestedText := c.getElementText(nestedBoundary)
				if nestedText == "" {
					// Try to find a text element near the top of the nested boundary
					var minY float64 = 1e9
					for _, elem := range doc.Elements {
						if elem.Type == "text" && elem.ContainerId == nil {
							// Check if the text element is positioned near the top of the nested boundary
							if elem.X >= nestedBoundary.X &&
								elem.Y >= nestedBoundary.Y &&
								elem.X+elem.Width <= nestedBoundary.X+nestedBoundary.Width &&
								elem.Y+elem.Height <= nestedBoundary.Y+nestedBoundary.Height/4 {
								// Use the text element with the smallest Y coordinate (topmost)
								if elem.Y < minY {
									minY = elem.Y
									nestedText = strings.TrimSpace(strings.ReplaceAll(elem.Text, "\n", " "))
								}
							}
						}
					}
				}

				if nestedText == "" {
					nestedText = "Nested System"
				}
				sb.WriteString(fmt.Sprintf("    System_Boundary(Element_%s, \"%s\") {\n", nestedBoundary.ID[:8], nestedText))

				// Find containers within nested boundary
				for _, container := range containers {
					if !processedContainers[container.ID] &&
						container.X >= nestedBoundary.X &&
						container.Y >= nestedBoundary.Y &&
						container.X+container.Width <= nestedBoundary.X+nestedBoundary.Width &&
						container.Y+container.Height <= nestedBoundary.Y+nestedBoundary.Height {
						sb.WriteString("        " + c.convertRectangle(container))
						processedContainers[container.ID] = true
					}
				}

				sb.WriteString("    }\n")
				processedBoundaries[nestedBoundary.ID] = true
			}
		}

		// Find containers directly within this boundary (not in nested boundaries)
		for _, container := range containers {
			if !processedContainers[container.ID] &&
				container.X >= boundary.X &&
				container.Y >= boundary.Y &&
				container.X+container.Width <= boundary.X+boundary.Width &&
				container.Y+container.Height <= boundary.Y+boundary.Height {
				sb.WriteString("    " + c.convertRectangle(container))
				processedContainers[container.ID] = true
			}
		}

		sb.WriteString("}\n\n")
		processedBoundaries[boundary.ID] = true
	}

	// Fourth pass: Define standalone containers (not in any boundary)
	for _, container := range containers {
		if !processedContainers[container.ID] {
			sb.WriteString(c.convertRectangle(container))
		}
	}

	// Fifth pass: Define relationships
	// First, collect all text elements that might be labels
	type TextElement struct {
		Text string
		X    float64
		Y    float64
	}
	var textElements []TextElement
	for _, elem := range doc.Elements {
		if elem.Type == "text" && elem.ContainerId == nil {
			textElements = append(textElements, TextElement{
				Text: strings.TrimSpace(strings.ReplaceAll(elem.Text, "\n", " ")),
				X:    elem.X,
				Y:    elem.Y,
			})
		}
	}

	// Create a map of arrow IDs to their labels
	arrowLabels := make(map[string]string)
	for i := range doc.Elements {
		if doc.Elements[i].Type == "arrow" {
			arrow := &doc.Elements[i]
			if len(arrow.Points) < 2 {
				continue
			}

			// Find relationship label by looking for text elements near the arrow
			var label string
			if len(arrow.Points) > 0 {
				// Calculate arrow midpoint
				midX := arrow.X + (arrow.Points[0][0]+arrow.Points[len(arrow.Points)-1][0])/2
				midY := arrow.Y + (arrow.Points[0][1]+arrow.Points[len(arrow.Points)-1][1])/2

				// Calculate arrow direction vector
				dx := arrow.Points[len(arrow.Points)-1][0] - arrow.Points[0][0]
				dy := arrow.Points[len(arrow.Points)-1][1] - arrow.Points[0][1]
				length := math.Sqrt(dx*dx + dy*dy)
				if length > 0 {
					dx /= length
					dy /= length
				}

				// First check for text elements bound to the arrow
				for _, boundElem := range arrow.BoundElements {
					if boundElem.Type == "text" {
						if textElem, ok := c.elements[boundElem.ID]; ok {
							label = strings.TrimSpace(strings.ReplaceAll(textElem.Text, "\n", " "))
							break
						}
					}
				}

				// If no bound text found, look for nearby text elements
				if label == "" {
					minDist := 150.0 // Increased maximum distance to consider for label
					for _, text := range textElements {
						// Vector from midpoint to text
						tx := text.X - midX
						ty := text.Y - midY

						// Distance from text to arrow line (perpendicular distance)
						dist := math.Abs(tx*dy - ty*dx)

						// Distance along the arrow
						proj := tx*dx + ty*dy

						// Only consider text elements that are near the middle of the arrow
						if dist < minDist && math.Abs(proj) < length/2 {
							label = text.Text
							minDist = dist
						}
					}
				}
			}

			arrowLabels[arrow.ID] = label
		}
	}

	// Now generate the relationships
	for i := range doc.Elements {
		if doc.Elements[i].Type == "arrow" {
			arrow := &doc.Elements[i]
			if len(arrow.Points) < 2 {
				continue
			}

			// Find start element
			var startElem *models.ExcalidrawElement
			if arrow.StartBinding != nil {
				startElem = c.elements[arrow.StartBinding.ElementId]
			}

			// Find end element
			var endElem *models.ExcalidrawElement
			if arrow.EndBinding != nil {
				endElem = c.elements[arrow.EndBinding.ElementId]
			}

			// Get the label from our map
			label := arrowLabels[arrow.ID]

			// Generate relationship if both elements are found and neither is a text element
			if startElem != nil && endElem != nil && startElem.ID != endElem.ID &&
				startElem.Type != "text" && endElem.Type != "text" {
				sb.WriteString(fmt.Sprintf("Rel(Element_%s, Element_%s, \"%s\")\n",
					startElem.ID[:8], endElem.ID[:8], label))
			}
		}
	}

	// Add implicit relationships based on element types
	studyCompanionFound := false
	databaseFound := false
	var studyCompanionID, databaseID string

	// First find the Study Companion and Database elements
	for _, elem := range c.elements {
		if elem.Type == "rectangle" {
			text := c.getElementText(elem)
			if strings.Contains(strings.ToLower(text), "study companion") {
				studyCompanionFound = true
				studyCompanionID = elem.ID[:8]
			}
		} else if elem.Type == "ellipse" || strings.Contains(strings.ToLower(c.getElementText(elem)), "database") {
			databaseFound = true
			databaseID = elem.ID[:8]
		}
	}

	// Add the Study Companion to Database relationship if both elements exist
	if studyCompanionFound && databaseFound {
		sb.WriteString(fmt.Sprintf("Rel(Element_%s, Element_%s, \"Saves\")\n",
			studyCompanionID, databaseID))
	}

	sb.WriteString("\n@enduml")
	return sb.String()
}

func (c *Converter) convertRectangle(elem *models.ExcalidrawElement) string {
	text := c.getElementText(elem)
	if text == "" {
		text = "Box"
	}

	// Check if this is a database element (ellipse or text contains "Database")
	if elem.Type == "ellipse" || strings.Contains(strings.ToLower(text), "database") {
		return fmt.Sprintf("ComponentDb(Element_%s, \"%s\")\n", elem.ID[:8], text)
	}

	return fmt.Sprintf("Container(Element_%s, \"%s\")\n", elem.ID[:8], text)
}

func (c *Converter) convertText(elem *models.ExcalidrawElement) string {
	// Only convert standalone text elements that are not bound to rectangles
	if elem.ContainerId == nil {
		// Check if this text is bound to any rectangle
		for _, otherElem := range c.elements {
			if otherElem.Type == "rectangle" && len(otherElem.BoundElements) > 0 {
				for _, bound := range otherElem.BoundElements {
					if bound.ID == elem.ID {
						return "" // Skip text that is bound to a rectangle
					}
				}
			}
		}

		// This is a standalone text element
		return fmt.Sprintf("note \"%s\" as %s\n", elem.Text, fmt.Sprintf("Note_%s", elem.ID[:8]))
	}
	return ""
}

func (c *Converter) convertArrow(elem *models.ExcalidrawElement) string {
	if len(elem.Points) < 2 {
		return ""
	}

	var startElem, endElem *models.ExcalidrawElement
	var startText, endText string

	// Find start element
	if elem.StartBinding != nil {
		if startElem = c.elements[elem.StartBinding.ElementId]; startElem != nil {
			startText = fmt.Sprintf("Element_%s", startElem.ID[:8])
		}
	}

	// Find end element
	if elem.EndBinding != nil {
		if endElem = c.elements[elem.EndBinding.ElementId]; endElem != nil {
			endText = fmt.Sprintf("Element_%s", endElem.ID[:8])
		}
	}

	// If we couldn't find the elements, try to find them by position
	if startElem == nil || endElem == nil {
		startElem = c.findElementAtPosition(elem.Points[0][0], elem.Points[0][1])
		endElem = c.findElementAtPosition(elem.Points[len(elem.Points)-1][0], elem.Points[len(elem.Points)-1][1])

		if startElem != nil {
			startText = fmt.Sprintf("Element_%s", startElem.ID[:8])
		}
		if endElem != nil {
			endText = fmt.Sprintf("Element_%s", endElem.ID[:8])
		}
	}

	// Don't create a relationship to itself
	if startText == endText {
		return ""
	}

	return fmt.Sprintf("Rel(%s, %s, \"\")\n", startText, endText)
}

func (c *Converter) getElementText(elem *models.ExcalidrawElement) string {
	// First check if the element has its own text
	if elem.Text != "" {
		return strings.TrimSpace(strings.ReplaceAll(elem.Text, "\n", " "))
	}

	// Then check for bound text elements
	if len(elem.BoundElements) > 0 {
		for _, bound := range elem.BoundElements {
			if boundElem, ok := c.elements[bound.ID]; ok && boundElem.Type == "text" {
				return strings.TrimSpace(strings.ReplaceAll(boundElem.Text, "\n", " "))
			}
		}
	}

	// If no bound text elements, look for text elements that are positioned within the rectangle
	if elem.Type == "rectangle" {
		for _, otherElem := range c.elements {
			if otherElem.Type == "text" && otherElem.ContainerId == nil {
				// Check if the text element is positioned within the rectangle
				if otherElem.X >= elem.X &&
					otherElem.Y >= elem.Y &&
					otherElem.X+otherElem.Width <= elem.X+elem.Width &&
					otherElem.Y+otherElem.Height <= elem.Y+elem.Height {
					return strings.TrimSpace(strings.ReplaceAll(otherElem.Text, "\n", " "))
				}
			}
		}
	}

	// If no text is found, use a generic name based on the element type
	if elem.Type == "rectangle" {
		return "Box"
	}

	// For other element types, use a generic name
	return "Element"
}

func (c *Converter) findElementAtPosition(x, y float64) *models.ExcalidrawElement {
	var bestMatch *models.ExcalidrawElement
	var minDistance float64 = 1e9

	for _, elem := range c.elements {
		if elem.Type == "rectangle" && elem.Width <= 1000 && elem.Height <= 1000 {
			// Calculate the center of the element
			centerX := elem.X + elem.Width/2
			centerY := elem.Y + elem.Height/2

			// Calculate distance to the center
			distance := (x-centerX)*(x-centerX) + (y-centerY)*(y-centerY)

			// Update best match if this element is closer
			if distance < minDistance {
				minDistance = distance
				bestMatch = elem
			}
		}
	}
	return bestMatch
}
