export type ProjectMode = "existing_repository" | "new_idea";

export type NewIdeaBrief = {
  problem: string;
  intended_user: string;
  first_outcome: string;
  constraints: string[];
};

export type SavedProject = {
  id: string;
  name: string;
  description: string;
  mode: ProjectMode;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
  last_activity_at: string;
  source: {
    mode: ProjectMode;
    repository_url: string | null;
    idea_brief: NewIdeaBrief | null;
  };
};

export type ProjectListResponse = {
  items: SavedProject[];
  next_cursor: string | null;
};
