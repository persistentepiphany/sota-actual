/**
 * JobsScreen — DEV/ADMIN PAGE ONLY
 * Not used in the user-facing mobile app.
 * Import this in a separate /dev or /admin route if needed.
 */
"use client";

import { useState, useEffect } from "react";

interface Job {
  id: string;
  type: "hotel" | "restaurant" | "call" | "generic";
  title: string;
  description: string;
  status: "open" | "bidding" | "assigned" | "completed";
  bidCount: number;
  priceRange: string;
  createdAt: string;
}

const TYPE_ICONS: Record<Job["type"], string> = {
  hotel: "🏨",
  restaurant: "🍽️",
  call: "📞",
  generic: "📦",
};

const STATUS_COLORS: Record<Job["status"], string> = {
  open: "chip-green",
  bidding: "chip-amber",
  assigned: "chip-blue",
  completed: "chip-gray",
};

// Placeholder data until /api/jobs is wired
const MOCK_JOBS: Job[] = [
  {
    id: "1",
    type: "hotel",
    title: "Book Ritz-Carlton London",
    description: "2 nights, king suite, March 22-24",
    status: "bidding",
    bidCount: 3,
    priceRange: "£450 – £620",
    createdAt: new Date().toISOString(),
  },
  {
    id: "2",
    type: "restaurant",
    title: "Reserve Nobu Mayfair",
    description: "Party of 4, Friday 8pm",
    status: "open",
    bidCount: 0,
    priceRange: "£0 (reservation)",
    createdAt: new Date().toISOString(),
  },
  {
    id: "3",
    type: "call",
    title: "Verify dentist appointment",
    description: "Call Dr. Smith's office, confirm Thursday 10am",
    status: "assigned",
    bidCount: 1,
    priceRange: "$5",
    createdAt: new Date().toISOString(),
  },
  {
    id: "4",
    type: "generic",
    title: "Compare car insurance quotes",
    description: "Get 3 quotes for 2024 Tesla Model 3",
    status: "completed",
    bidCount: 5,
    priceRange: "$80 – $120/mo",
    createdAt: new Date().toISOString(),
  },
];

export default function JobsScreen() {
  const [jobs, setJobs] = useState<Job[]>(MOCK_JOBS);
  const [filter, setFilter] = useState<Job["status"] | "all">("all");

  // TODO: replace with real fetch from /api/jobs
  // useEffect(() => {
  //   fetch("/api/jobs").then(r => r.json()).then(setJobs);
  // }, []);

  const filtered = filter === "all" ? jobs : jobs.filter((j) => j.status === filter);

  return (
    <div className="jobs-screen">
      <h2 className="screen-title">Job Marketplace</h2>

      {/* Filter pills */}
      <div className="filter-row">
        {(["all", "open", "bidding", "assigned", "completed"] as const).map((f) => (
          <button
            key={f}
            className={`filter-pill ${filter === f ? "active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Job cards */}
      <div className="jobs-list">
        {filtered.map((job) => (
          <div key={job.id} className="job-card">
            <div className="job-card-header">
              <span className="job-type-icon">{TYPE_ICONS[job.type]}</span>
              <h3 className="job-title">{job.title}</h3>
              <span className={`job-status-chip ${STATUS_COLORS[job.status]}`}>
                {job.status}
              </span>
            </div>
            <p className="job-desc">{job.description}</p>
            <div className="job-card-footer">
              <span className="job-meta">💰 {job.priceRange}</span>
              <span className="job-meta">🏷️ {job.bidCount} bids</span>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <p className="empty-state">No jobs match this filter.</p>
        )}
      </div>
    </div>
  );
}
