// KnowMe D3.js Force-Directed Graph Visualization

function renderKnowledgeGraph(containerId, graphData, activeMode, onNodeClick) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    // Clear previous graph
    container.innerHTML = "";
    
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;
    
    const svg = d3.select(`#${containerId}`)
        .append("svg")
        .attr("class", "graph-svg")
        .attr("viewBox", `0 0 ${width} ${height}`)
        .attr("width", "100%")
        .attr("height", "100%");
        
    // Add arrow markers for prerequisite directed links
    svg.append("defs").append("marker")
        .attr("id", "arrow")
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 20)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", "#f97316"); // Prerequisite orange arrow
        
    const g = svg.append("g");
    
    // Zoom behavior
    const zoom = d3.zoom()
        .scaleExtent([0.2, 4])
        .on("zoom", (event) => {
            g.attr("transform", event.transform);
        });
        
    svg.call(zoom);
    
    // Calculate degree (connection count) for each node to determine size
    const nodeDegrees = {};
    graphData.nodes.forEach(n => nodeDegrees[n.id] = 0);
    graphData.edges.forEach(e => {
        if (nodeDegrees[e.source] !== undefined) nodeDegrees[e.source]++;
        if (nodeDegrees[e.target] !== undefined) nodeDegrees[e.target]++;
    });
    
    // Setup D3 force simulation
    const simulation = d3.forceSimulation(graphData.nodes)
        .force("link", d3.forceLink(graphData.edges).id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody().strength(-200))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(d => (8 + (nodeDegrees[d.id] || 0) * 3) + 10));
        
    // Edge color encoding
    const getEdgeColor = (d) => {
        if (d.is_prerequisite) return "#f97316"; // Orange
        if (d.type === "CONTRADICTS") return "#ef4444"; // Red
        if (d.type === "IS-ANALOGOUS-TO") return "#8b5cf6"; // Purple
        return "#3b82f6"; // Blue semantic
    };
    
    // Draw links (edges)
    const link = g.append("g")
        .attr("class", "links")
        .selectAll("line")
        .data(graphData.edges)
        .enter()
        .append("line")
        .attr("class", "link")
        .attr("stroke", d => getEdgeColor(d))
        .attr("stroke-dasharray", d => d.is_prerequisite ? "4,4" : "0")
        .attr("marker-end", d => d.is_prerequisite ? "url(#arrow)" : "none");
        
    // Dimming filter logic
    const isMatchingFilter = (node) => {
        if (!activeMode) return true;
        const status = node.status;
        const isGhost = node.ghost;
        
        switch (activeMode) {
            case "STABILIZATION":
                return status >= 4;
            case "RECOVERY":
                return status >= 3;
            case "CONSOLIDATION":
                return status >= 2 && status <= 4;
            case "PROGRESSION":
                return isGhost || status <= 1;
            case "PEAK":
            default:
                return true;
        }
    };
    
    // Color coding for note status
    const getStatusColor = (status) => {
        switch (status) {
            case 0: return "#4b5563"; // Grey
            case 1: return "#1e3a8a"; // Dim Blue
            case 2: return "#2563eb"; // Mid Blue
            case 3: return "#60a5fa"; // Bright Blue
            case 4: return "#10b981"; // Green
            case 5: return "#d97706"; // Gold
            default: return "#4b5563";
        }
    };
    
    // Tooltip selection
    let tooltip = d3.select("#graph-tooltip");
    if (tooltip.empty()) {
        tooltip = d3.select("body")
            .append("div")
            .attr("id", "graph-tooltip")
            .attr("class", "tooltip");
    }
    
    // Draw nodes
    const node = g.append("g")
        .attr("class", "nodes")
        .selectAll("g")
        .data(graphData.nodes)
        .enter()
        .append("g")
        .attr("class", "node")
        .call(d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended))
        .on("click", (event, d) => {
            // Prevent triggering on drag
            if (event.defaultPrevented) return;
            onNodeClick(d.id);
        })
        .on("mouseover", (event, d) => {
            tooltip.style("opacity", 1)
                .html(`
                    <strong>${d.name}</strong><br/>
                    Type: ${d.type}<br/>
                    Mastery: Level ${d.status} (${getStatusLabel(d.status)})<br/>
                    ${d.ghost ? "👻 <em>Ghost Note (debt)</em>" : ""}
                `)
                .style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 28) + "px");
        })
        .on("mousemove", (event) => {
            tooltip.style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", () => {
            tooltip.style("opacity", 0);
        });
        
    // Circle rendering inside nodes
    node.append("circle")
        .attr("r", d => 8 + (nodeDegrees[d.id] || 0) * 3)
        .attr("fill", d => d.ghost ? "transparent" : getStatusColor(d.status))
        .attr("stroke", d => getStatusColor(d.status))
        .attr("stroke-width", d => d.ghost ? 2 : 1)
        .attr("stroke-dasharray", d => d.ghost ? "3,3" : "0");
        
    // Add label text to nodes
    node.append("text")
        .attr("dx", d => (8 + (nodeDegrees[d.id] || 0) * 3) + 5)
        .attr("dy", ".35em")
        .text(d => d.name)
        .attr("fill", "#f3f4f6")
        .style("font-size", "11px")
        .style("font-weight", d => d.ghost ? "normal" : "600")
        .style("pointer-events", "none");
        
    // Apply dimming opacity based on matching filter
    node.each(function(d) {
        const matching = isMatchingFilter(d);
        if (!matching) {
            d3.select(this).classed("dimmed", true);
            // Also dim connected links
            link.filter(l => l.source.id === d.id || l.target.id === d.id).classed("dimmed", true);
        }
    });
    
    // Add pulsing CSS to ghost nodes if mode is PROGRESSION
    if (activeMode === "PROGRESSION") {
        node.filter(d => d.ghost)
            .select("circle")
            .style("animation", "pulse-glow 2s infinite");
    }
    
    // Update visual positions on tick
    simulation.on("tick", () => {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);
            
        node
            .attr("transform", d => `translate(${d.x}, ${d.y})`);
    });
    
    function getStatusLabel(status) {
        const labels = ["Heard", "Familiar", "Defined", "Connected", "Applicable", "Integrated"];
        return labels[status] || "Heard";
    }
    
    // Drag functions
    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }
    
    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }
    
    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
}
