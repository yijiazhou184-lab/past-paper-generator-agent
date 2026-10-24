import {
  createBrowserRouter,
  Navigate,
  Outlet,
  useLocation,
  useOutletContext,
  Link,
} from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Files,
  SlidersHorizontal,
  FileCheck2,
  LibraryBig,
  ArrowRight,
  Activity,
} from "lucide-react";
import { api } from "../api/client";
import type { Course, Session, Task } from "../api/types";
import { MaterialsPage } from "../features/materials/MaterialsPage";
import { TaskPage } from "../features/tasks/TaskPage";
import { ProfilePage } from "../features/profile/ProfilePage";
import { GeneratePage } from "../features/generate/GeneratePage";

export const useCourse = () => useOutletContext<Course>();
function Workspace() {
  const cache = useQueryClient();
  const location = useLocation();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: () => api<Session>("/session"),
  });
  const enter = useMutation({
    mutationFn: () => api("/session", { method: "POST" }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["session"] }),
  });
  const courses = useQuery({
    queryKey: ["courses"],
    queryFn: () => api<{ courses: Course[] }>("/courses"),
    enabled: session.data?.authenticated === true,
  });
  const requestedTask = location.pathname.match(/^\/tasks\/([^/]+)/)?.[1];
  const taskContext = useQuery({
    queryKey: ["task", requestedTask],
    queryFn: () => api<Task>(`/tasks/${requestedTask}`),
    enabled: !!requestedTask && session.data?.authenticated === true,
  });
  if (session.isPending)
    return (
      <div className="welcome">
        <BookOpen />
        <h1>Opening your workspace…</h1>
      </div>
    );
  if (session.isError)
    return (
      <div className="welcome">
        <h1>Workspace unavailable</h1>
        <p>{session.error.message}</p>
        <button onClick={() => session.refetch()}>Try again</button>
      </div>
    );
  if (!session.data.authenticated)
    return (
      <div className="welcome">
        <span className="brand-icon">
          <BookOpen size={28} />
        </span>
        <h1>Your course. Your next practice.</h1>
        <p>
          Bring your course materials together, check their sources, and prepare
          for a more focused practice session.
        </p>
        <button
          className="primary"
          onClick={() => enter.mutate()}
          disabled={enter.isPending}
        >
          Open local workspace <ArrowRight size={18} />
        </button>
        <small>
          Private workspace on this computer. Review the selected sources before analysis.
        </small>
        {enter.isError && <p role="alert">{enter.error.message}</p>}
      </div>
    );
  if (courses.isError)
    return (
      <div className="welcome">
        <h1>Could not load your course</h1>
        <p>{courses.error.message}</p>
        <button onClick={() => courses.refetch()}>Retry</button>
      </div>
    );
  if (requestedTask && taskContext.isPending)
    return <div className="welcome"><h1>Loading task workspace…</h1></div>;
  if (requestedTask && taskContext.isError)
    return <div className="welcome"><h1>Could not load this task</h1><p>{taskContext.error.message}</p><button onClick={() => taskContext.refetch()}>Retry</button><Link to="/">Return to workspace</Link></div>;
  const requestedCourse = location.pathname.match(/^\/courses\/([^/]+)/)?.[1] ?? taskContext.data?.course_id;
  const course = requestedCourse ? courses.data?.courses.find(c => c.id === requestedCourse) : courses.data?.courses[0];
  if (!course)
    return (
      <div className="welcome">
        <h1>Loading course…</h1>
      </div>
    );
  return (
    <div className="workspace">
      <aside className="sidebar">
        <Link to={`/courses/${course.id}/materials`} className="brand">
          <span className="brand-icon">
            <BookOpen size={22} />
          </span>
          <span>
            Past Paper
            <br />
            <strong>Generator</strong>
          </span>
        </Link>
        <div className="course-label">Your workspace</div>
        <div className="course-name">
          {course.title}
          <small>{course.code}</small>
        </div>
        <nav aria-label="Course navigation">
          <Link
            className={
              location.pathname.includes("materials")
                ? "nav-item active"
                : "nav-item"
            }
            to={`/courses/${course.id}/materials`}
          >
            <Files size={19} />
            Materials
          </Link>
          <Link className={location.pathname.includes("profile") ? "nav-item active" : "nav-item"} to={`/courses/${course.id}/profile`}>
            <FileCheck2 size={19} />
            Course profile
          </Link>
          <Link className={location.pathname.includes("generate") ? "nav-item active" : "nav-item"} to={`/courses/${course.id}/generate`}>
            <SlidersHorizontal size={19} />
            Generate
          </Link>
          <span className="nav-item disabled" title="No generated papers yet">
            <LibraryBig size={19} />
            Papers
          </span>
        </nav>
        <div className="sidebar-footer">
          <span className="online-dot" /> Local workspace
          <small>Materials, course profile and practice</small>
        </div>
      </aside>
      <div className="workspace-body">
        <header className="topbar">
          <span>
            {course.code} <span className="slash">/</span> {course.title}
          </span>
          <span className="local-chip">
            <Activity size={14} />
            Saved on this computer
          </span>
        </header>
        <main>
          <Outlet context={course} />
        </main>
      </div>
    </div>
  );
}
function Home() {
  const course = useCourse();
  return <Navigate replace to={`/courses/${course.id}/materials`} />;
}
export const router = createBrowserRouter([
  {
    element: <Workspace />,
    errorElement: (
      <div className="welcome">
        <h1>This page could not be opened</h1>
        <a href="/">Return to workspace</a>
      </div>
    ),
    children: [
      { path: "/", element: <Home /> },
      { path: "/courses/:courseId/materials", element: <MaterialsPage /> },
      { path: "/courses/:courseId/profile", element: <ProfilePage /> },
      { path: "/courses/:courseId/generate", element: <GeneratePage /> },
      { path: "/tasks/:taskId", element: <TaskPage /> },
    ],
  },
]);
